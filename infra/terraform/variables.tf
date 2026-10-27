variable "region" {
  type    = string
  default = "us-east-1"
}
variable "name" {
  type    = string
  default = "riceflow-demo"
}
variable "bucket_name" {
  type = string
}
variable "budget_email" {
  type        = string
  description = "User-provided email required before deployment. No placeholder recipient."
  validation {
    condition     = can(regex("^[^@]+@[^@]+[.][^@]+$", var.budget_email))
    error_message = "Provide a real budget notification email."
  }
}
variable "controller_ami" {
  type        = string
  description = "Reviewed x86_64 Amazon Linux 2023 AMI in selected region; never use an unreviewed latest AMI."
}
variable "max_vcpus" {
  type    = number
  default = 2
  validation {
    condition     = var.max_vcpus >= 2 && var.max_vcpus <= 4
    error_message = "Demo maximum must be 2–4 vCPUs."
  }
}
