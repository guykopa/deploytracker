resource "aws_ssm_parameter" "db_password" {
  name  = "/deploytracker/db_password"
  type  = "SecureString"
  value = var.db_password
}

resource "aws_ssm_parameter" "grafana_admin_password" {
  name  = "/deploytracker/grafana_admin_password"
  type  = "SecureString"
  value = var.grafana_admin_password
}

resource "aws_ssm_parameter" "k3s_token" {
  name  = "/deploytracker/k3s_token"
  type  = "SecureString"
  value = var.k3s_token
}
