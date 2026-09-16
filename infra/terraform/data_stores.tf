resource "random_password" "db" {
  length  = 24
  special = false
}

resource "aws_db_subnet_group" "this" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "this" {
  identifier                   = var.name
  engine                       = "postgres"
  engine_version               = "16.4"
  instance_class               = "db.t4g.micro"
  allocated_storage            = 20
  db_name                      = "pulsestream"
  username                     = var.db_username
  password                     = random_password.db.result
  db_subnet_group_name         = aws_db_subnet_group.this.name
  vpc_security_group_ids       = [aws_security_group.rds.id]
  publicly_accessible          = false
  skip_final_snapshot          = true
  deletion_protection          = false
  backup_retention_period      = 1
  apply_immediately            = true
  performance_insights_enabled = false
}

resource "aws_elasticache_subnet_group" "this" {
  name       = var.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_elasticache_cluster" "this" {
  cluster_id           = var.name
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = "cache.t4g.micro"
  num_cache_nodes      = 1
  port                 = 6379
  parameter_group_name = "default.redis7"
  subnet_group_name    = aws_elasticache_subnet_group.this.name
  security_group_ids   = [aws_security_group.redis.id]
}

resource "aws_secretsmanager_secret" "app" {
  name = "${var.name}/app"
}

resource "aws_secretsmanager_secret_version" "app" {
  secret_id = aws_secretsmanager_secret.app.id
  secret_string = jsonencode({
    database_url        = "postgresql://${var.db_username}:${random_password.db.result}@${aws_db_instance.this.address}:5432/pulsestream?sslmode=require"
    redis_url           = "redis://${aws_elasticache_cluster.this.cache_nodes[0].address}:6379/0"
    celery_broker_url   = "redis://${aws_elasticache_cluster.this.cache_nodes[0].address}:6379/1"
    kafka_sasl_password = var.kafka_sasl_password
  })
}
