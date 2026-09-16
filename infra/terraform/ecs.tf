locals {
  common_environment = concat(
    [
      { name = "KAFKA_BOOTSTRAP_SERVERS", value = var.kafka_bootstrap_servers },
      { name = "KAFKA_SECURITY_PROTOCOL", value = var.kafka_security_protocol },
      { name = "KAFKA_REPLICATION_FACTOR", value = tostring(var.kafka_replication_factor) },
      { name = "LOG_LEVEL", value = "INFO" },
    ],
    var.kafka_sasl_mechanism != "" ? [
      { name = "KAFKA_SASL_MECHANISM", value = var.kafka_sasl_mechanism },
      { name = "KAFKA_SASL_USERNAME", value = var.kafka_sasl_username },
    ] : []
  )

  common_secrets = concat(
    [
      {
        name      = "DATABASE_URL"
        valueFrom = "${aws_secretsmanager_secret.app.arn}:database_url::"
      },
      {
        name      = "REDIS_URL"
        valueFrom = "${aws_secretsmanager_secret.app.arn}:redis_url::"
      },
      {
        name      = "CELERY_BROKER_URL"
        valueFrom = "${aws_secretsmanager_secret.app.arn}:celery_broker_url::"
      },
    ],
    var.kafka_sasl_mechanism != "" ? [
      {
        name      = "KAFKA_SASL_PASSWORD"
        valueFrom = "${aws_secretsmanager_secret.app.arn}:kafka_sasl_password::"
      }
    ] : []
  )

  python_services = {
    ingestion-api = {
      command = ["uvicorn", "services.ingestion_api.app:app", "--host", "0.0.0.0", "--port", "8000"]
      port    = 8000
      desired = 1
    }
    analytics-api = {
      command = ["uvicorn", "services.analytics_api.app:app", "--host", "0.0.0.0", "--port", "8001"]
      port    = 8001
      desired = 1
    }
    event-consumer = {
      command = ["python", "-m", "services.event_consumer.app"]
      port    = 8002
      desired = 1
    }
    celery-worker = {
      command = ["celery", "-A", "services.celery_worker.celery_app", "worker", "--loglevel=INFO"]
      port    = null
      desired = 1
    }
    celery-beat = {
      command = ["celery", "-A", "services.celery_worker.celery_app", "beat", "--loglevel=INFO", "--schedule=/tmp/celerybeat-schedule"]
      port    = null
      desired = 1
    }
  }
}

resource "aws_cloudwatch_log_group" "this" {
  name              = "/ecs/${var.name}"
  retention_in_days = 14
}

resource "aws_ecs_cluster" "this" {
  name = var.name

  setting {
    name  = "containerInsights"
    value = "disabled"
  }
}

resource "aws_ecs_task_definition" "python" {
  for_each                 = local.python_services
  family                   = "${var.name}-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = each.key
      image     = "${aws_ecr_repository.app.repository_url}:latest"
      essential = true
      command   = each.value.command
      portMappings = each.value.port == null ? [] : [
        {
          containerPort = each.value.port
          hostPort      = each.value.port
          protocol      = "tcp"
        }
      ]
      environment = local.common_environment
      secrets     = local.common_secrets
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = each.key
        }
      }
    }
  ])
}

resource "aws_ecs_task_definition" "dashboard" {
  family                   = "${var.name}-dashboard"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "dashboard"
      image     = "${aws_ecr_repository.dashboard.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 80
          hostPort      = 80
          protocol      = "tcp"
        }
      ]
      environment = [
        { name = "ANALYTICS_HOST", value = "analytics-api" }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "dashboard"
        }
      }
    }
  ])
}

resource "aws_ecs_service" "python" {
  for_each        = local.python_services
  name            = each.key
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.python[each.key].arn
  desired_count   = each.value.desired
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  dynamic "load_balancer" {
    for_each = each.key == "ingestion-api" ? [aws_lb_target_group.ingestion.arn] : each.key == "analytics-api" ? [aws_lb_target_group.analytics.arn] : []
    content {
      target_group_arn = load_balancer.value
      container_name   = each.key
      container_port   = each.value.port
    }
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  depends_on = [aws_lb_listener.http]
}

resource "aws_ecs_service" "dashboard" {
  name            = "dashboard"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.dashboard.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.dashboard.arn
    container_name   = "dashboard"
    container_port   = 80
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  depends_on = [aws_lb_listener.http]
}
