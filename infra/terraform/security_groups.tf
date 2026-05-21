resource "aws_security_group" "k3s_common" {
  name   = "k3s-common"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group" "k3s_server" {
  name   = "k3s-server"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group" "k3s_agent" {
  name   = "k3s-agent"
  vpc_id = aws_vpc.main.id
}

resource "aws_security_group_rule" "common_kubelet_ingress" {
  type                     = "ingress"
  from_port                = 10250
  to_port                  = 10250
  protocol                 = "tcp"
  security_group_id        = aws_security_group.k3s_common.id
  source_security_group_id = aws_security_group.k3s_common.id
}

resource "aws_security_group_rule" "common_flannel_ingress" {
  type                     = "ingress"
  from_port                = 8472
  to_port                  = 8472
  protocol                 = "udp"
  security_group_id        = aws_security_group.k3s_common.id
  source_security_group_id = aws_security_group.k3s_common.id
}

resource "aws_security_group_rule" "common_k3s_api_ingress" {
  type                     = "ingress"
  from_port                = 6443
  to_port                  = 6443
  protocol                 = "tcp"
  security_group_id        = aws_security_group.k3s_common.id
  source_security_group_id = aws_security_group.k3s_common.id
}

resource "aws_security_group_rule" "common_registry_ingress" {
  type                     = "ingress"
  from_port                = 5001
  to_port                  = 5001
  protocol                 = "tcp"
  security_group_id        = aws_security_group.k3s_common.id
  source_security_group_id = aws_security_group.k3s_common.id
}

resource "aws_security_group_rule" "common_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.k3s_common.id
}

resource "aws_security_group_rule" "server_ssh_ingress" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = ["88.123.247.103/32"]
  security_group_id = aws_security_group.k3s_server.id
}

resource "aws_security_group_rule" "server_kubectl_ingress" {
  type              = "ingress"
  from_port         = 6443
  to_port           = 6443
  protocol          = "tcp"
  cidr_blocks       = ["88.123.247.103/32"]
  security_group_id = aws_security_group.k3s_server.id
}

resource "aws_security_group_rule" "server_nodeport_ingress" {
  type              = "ingress"
  from_port         = 30000
  to_port           = 32767
  protocol          = "tcp"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.k3s_server.id
}

resource "aws_security_group_rule" "server_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.k3s_server.id
}

resource "aws_security_group_rule" "agent_ssh_ingress_server" {
  type                     = "ingress"
  from_port                = 22
  to_port                  = 22
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.k3s_server.id
  security_group_id        = aws_security_group.k3s_agent.id
}

resource "aws_security_group_rule" "agent_ssh_ingress_developer" {
  type              = "ingress"
  from_port         = 22
  to_port           = 22
  protocol          = "tcp"
  cidr_blocks       = ["88.123.247.103/32"]
  security_group_id = aws_security_group.k3s_agent.id
}

resource "aws_security_group_rule" "agent_egress" {
  type              = "egress"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
  security_group_id = aws_security_group.k3s_agent.id
}
