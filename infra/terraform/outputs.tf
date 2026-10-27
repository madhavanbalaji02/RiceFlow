output "bucket" { value = aws_s3_bucket.data.id }
output "queue" { value = aws_batch_job_queue.cpu.arn }
output "compute_environment" { value = aws_batch_compute_environment.cpu.arn }
output "image_repository" { value = aws_ecr_repository.workflow.repository_url }
output "task_role" { value = aws_iam_role.task.arn }
output "log_group" { value = aws_cloudwatch_log_group.jobs.name }
output "controller_id" { value = aws_instance.controller.id }
output "worker_profile" { value = aws_iam_instance_profile.worker.name }
