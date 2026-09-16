variable "aws_region" {
  type        = string
  description = "AWS region for ECR, ECS, RDS, and ElastiCache."
  default     = "us-east-1"
}

variable "name" {
  type    = string
  default = "pulsestream"
}

variable "github_repository" {
  type        = string
  description = "GitHub org/repo allowed to assume the deploy role via OIDC."
  default     = "Frank20021/PulseStream"
}

variable "kafka_bootstrap_servers" {
  type        = string
  description = "Existing managed Kafka bootstrap, for example MSK or Confluent."
}

variable "kafka_security_protocol" {
  type    = string
  default = "PLAINTEXT"
}

variable "kafka_sasl_mechanism" {
  type    = string
  default = ""
}

variable "kafka_sasl_username" {
  type    = string
  default = ""
}

variable "kafka_sasl_password" {
  type      = string
  default   = ""
  sensitive = true
}

variable "kafka_replication_factor" {
  type    = number
  default = 3
}

variable "db_username" {
  type    = string
  default = "pulsestream"
}
