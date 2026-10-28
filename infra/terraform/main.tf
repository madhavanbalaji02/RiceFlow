resource "aws_vpc" "demo" {
  cidr_block           = "10.83.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
}
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.demo.id
  cidr_block              = "10.83.1.0/24"
  map_public_ip_on_launch = true
}
resource "aws_internet_gateway" "demo" {
  vpc_id = aws_vpc.demo.id
}
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.demo.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.demo.id
  }
}
resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}
resource "aws_security_group" "demo" {
  name   = var.name
  vpc_id = aws_vpc.demo.id
  # No ingress. SSM, S3, ECR and Batch use outbound HTTPS via public IPv4/IGW; no NAT/endpoints.
  egress {
    protocol    = "-1"
    from_port   = 0
    to_port     = 0
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_s3_bucket" "data" {
  bucket        = var.bucket_name
  force_destroy = false
  lifecycle { prevent_destroy = true }
}
resource "aws_s3_bucket_public_access_block" "data" {
  bucket                  = aws_s3_bucket.data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}
resource "aws_s3_bucket_lifecycle_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    id     = "work-resume-30-days"
    status = "Enabled"
    filter { prefix = "work/" }
    expiration { days = 30 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
  rule {
    id     = "controller-cache-30-days"
    status = "Enabled"
    filter { prefix = "controller-backups/" }
    expiration { days = 30 }
  }
}
resource "aws_ecr_repository" "workflow" {
  name                 = var.name
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  force_delete = false
}
resource "aws_ecr_lifecycle_policy" "workflow" {
  repository = aws_ecr_repository.workflow.name
  policy = jsonencode({ rules = [{ rulePriority = 1, description = "Delete untagged after 7 days", selection = {
    tagStatus = "untagged", countType = "sinceImagePushed", countUnit = "days", countNumber = 7
  }, action = { type = "expire" } }] })
}
resource "aws_cloudwatch_log_group" "jobs" {
  name              = "/aws/batch/${var.name}"
  retention_in_days = 7
}
resource "aws_iam_role" "worker" {
  name = "${var.name}-worker"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole",
  Principal = { Service = "ec2.amazonaws.com" } }] })
}
resource "aws_iam_role_policy_attachment" "ecs" {
  role       = aws_iam_role.worker.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceforEC2Role"
}
resource "aws_iam_instance_profile" "worker" {
  name = "${var.name}-worker"
  role = aws_iam_role.worker.name
}
resource "aws_iam_role" "task" {
  name = "${var.name}-task"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole",
  Principal = { Service = "ecs-tasks.amazonaws.com" } }] })
}
resource "aws_iam_role_policy" "data" {
  for_each = { task = aws_iam_role.task.id, worker = aws_iam_role.worker.id, controller = aws_iam_role.controller.id }
  role     = each.value
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:GetBucketLocation", "s3:ListBucket"], Resource = aws_s3_bucket.data.arn },
    { Effect = "Allow", Action = ["s3:GetObject"], Resource = ["${aws_s3_bucket.data.arn}/inputs/*", "${aws_s3_bucket.data.arn}/reference/*"] },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"], Resource = ["${aws_s3_bucket.data.arn}/work/*", "${aws_s3_bucket.data.arn}/results/*", "${aws_s3_bucket.data.arn}/controller-backups/*"] },
    { Effect = "Allow", Action = ["ecr:GetAuthorizationToken"], Resource = "*" },
    { Effect = "Allow", Action = ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer", "ecr:BatchCheckLayerAvailability"], Resource = aws_ecr_repository.workflow.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.jobs.arn}:*" }
  ] })
}
resource "aws_iam_role" "batch" {
  name = "${var.name}-batch"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{ Effect = "Allow", Action = "sts:AssumeRole",
  Principal = { Service = "batch.amazonaws.com" } }] })
}
resource "aws_iam_role_policy_attachment" "batch" {
  role       = aws_iam_role.batch.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSBatchServiceRole"
}
resource "aws_launch_template" "worker" {
  name_prefix = var.name
  block_device_mappings {
    device_name = "/dev/xvda"
    ebs {
      volume_size           = 30
      volume_type           = "gp3"
      encrypted             = true
      delete_on_termination = true
    }
  }
  tag_specifications {
    resource_type = "volume"
    tags          = { Project = "RiceFlow" }
  }
  metadata_options {
    http_tokens                 = "required"
    http_put_response_hop_limit = 2
  }
}
resource "aws_batch_compute_environment" "cpu" {
  name         = var.name
  type         = "MANAGED"
  state        = "ENABLED"
  service_role = aws_iam_role.batch.arn
  compute_resources {
    type = "EC2"
    ec2_configuration { image_type = "ECS_AL2023" }
    allocation_strategy = "BEST_FIT_PROGRESSIVE"
    min_vcpus           = 0
    max_vcpus           = var.max_vcpus
    instance_type       = ["c6i.large"]
    instance_role       = aws_iam_instance_profile.worker.arn
    subnets             = [aws_subnet.public.id]
    security_group_ids  = [aws_security_group.demo.id]
    launch_template {
      launch_template_id = aws_launch_template.worker.id
      version            = "$Latest"
    }
    tags = { Project = "RiceFlow" }
  }
  depends_on = [aws_iam_role_policy_attachment.batch, aws_iam_role_policy_attachment.ecs,
  aws_route_table_association.public]
}
resource "aws_batch_job_queue" "cpu" {
  name     = var.name
  state    = "ENABLED"
  priority = 1
  compute_environment_order {
    order               = 1
    compute_environment = aws_batch_compute_environment.cpu.arn
  }
}
resource "aws_iam_role" "controller" {
  name               = "${var.name}-controller"
  assume_role_policy = aws_iam_role.worker.assume_role_policy
}
resource "aws_iam_role_policy_attachment" "ssm" {
  role       = aws_iam_role.controller.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
resource "aws_iam_instance_profile" "controller" {
  name = "${var.name}-controller"
  role = aws_iam_role.controller.name
}
resource "aws_iam_role_policy" "controller" {
  role = aws_iam_role.controller.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["batch:SubmitJob"], Resource = [aws_batch_job_queue.cpu.arn, "arn:aws:batch:${var.region}:*:job-definition/nf-*"] },
    { Effect = "Allow", Action = ["batch:TagResource"], Resource = ["arn:aws:batch:${var.region}:*:job-definition/nf-*", "arn:aws:batch:${var.region}:*:job/*"] },
    { Effect = "Allow", Action = ["batch:RegisterJobDefinition", "batch:DescribeJobDefinitions", "batch:DescribeJobs", "batch:DescribeJobQueues", "batch:DescribeComputeEnvironments", "batch:ListJobs", "batch:TerminateJob", "batch:CancelJob"], Resource = "*" },
    { Effect = "Allow", Action = ["ec2:DescribeInstances"], Resource = "*" },
    { Effect = "Allow", Action = ["iam:PassRole"], Resource = aws_iam_role.task.arn, Condition = { StringEquals = { "iam:PassedToService" = "ecs-tasks.amazonaws.com" } } }
  ] })
}
resource "aws_instance" "controller" {
  lifecycle {
    # A stopped instance releases its ephemeral public IP; preserve its root disk/cache on refresh.
    ignore_changes = [associate_public_ip_address]
  }
  ami                                  = var.controller_ami
  instance_type                        = "t3.small"
  subnet_id                            = aws_subnet.public.id
  vpc_security_group_ids               = [aws_security_group.demo.id]
  associate_public_ip_address          = true
  iam_instance_profile                 = aws_iam_instance_profile.controller.name
  instance_initiated_shutdown_behavior = "stop"
  metadata_options { http_tokens = "required" }
  root_block_device {
    volume_size           = 16
    volume_type           = "gp3"
    encrypted             = true
    delete_on_termination = false
  }
  volume_tags = { Project = "RiceFlow" }
  credit_specification { cpu_credits = "standard" }
  user_data = <<-SH
    #!/bin/bash
    set -eu
    mkdir -p /opt/riceflow-controller
    # Persistent root disk holds the launch directory, .nextflow cache/history and toolchain.
    # Install the reviewed toolchain and run scripts/cloud-controller.py only after cost authorization.
  SH
  tags      = { Name = "${var.name}-controller" }
}
resource "aws_budgets_budget" "monthly" {
  name         = var.name
  budget_type  = "COST"
  limit_amount = "15"
  limit_unit   = "USD"
  time_unit    = "MONTHLY"
  cost_types {
    include_credit = false
    include_refund = false
    include_tax    = false
  }
  cost_filter {
    name   = "TagKeyValue"
    values = ["user:Project$RiceFlow"]
  }
  dynamic "notification" {
    for_each = [5, 10, 15]
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value
      threshold_type             = "ABSOLUTE_VALUE"
      notification_type          = "ACTUAL"
      subscriber_email_addresses = [var.budget_email]
    }
  }
}
