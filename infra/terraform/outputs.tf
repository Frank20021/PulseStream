output "alb_dns_name" {
  value       = aws_lb.this.dns_name
  description = "Public load balancer. Dashboard is /, events are POST /api/v1/events."
}

output "ecr_app_url" {
  value = aws_ecr_repository.app.repository_url
}

output "ecr_dashboard_url" {
  value = aws_ecr_repository.dashboard.repository_url
}

output "github_actions_role_arn" {
  value       = aws_iam_role.github_actions.arn
  description = "Set this as the GitHub Actions secret AWS_ROLE_ARN."
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.this.name
}

output "rds_endpoint" {
  value = aws_db_instance.this.address
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.this.cache_nodes[0].address
}
