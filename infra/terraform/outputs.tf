output "k3s_server_public_ip" {
  description = "Public Elastic IP address of the K3s server"
  value       = aws_eip.k3s_server.public_ip
}

output "k3s_server_private_ip" {
  description = "Private IP address of the K3s server"
  value       = aws_instance.k3s_server.private_ip
}

output "k3s_agent1_private_ip" {
  description = "Private IP address of K3s agent 1"
  value       = aws_instance.k3s_agent1.private_ip
}

output "k3s_agent2_private_ip" {
  description = "Private IP address of K3s agent 2"
  value       = aws_instance.k3s_agent2.private_ip
}

output "ecr_repository_url" {
  description = "Full URL of the ECR repository"
  value       = aws_ecr_repository.deploytracker.repository_url
}

output "aws_account_id" {
  description = "AWS account ID"
  value       = "378202225330"
}
