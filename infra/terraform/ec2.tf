data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*"]
  }
}

resource "aws_instance" "k3s_server" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.small"
  subnet_id              = aws_subnet.public.id
  key_name               = "cle-ssh"
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  vpc_security_group_ids = [
    aws_security_group.k3s_common.id,
    aws_security_group.k3s_server.id,
  ]

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }

  tags = {
    Name = "k3s-server"
    Role = "k3s-server"
  }
}

resource "aws_instance" "k3s_agent1" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.small"
  subnet_id              = aws_subnet.public.id
  key_name               = "cle-ssh"
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  vpc_security_group_ids = [
    aws_security_group.k3s_common.id,
    aws_security_group.k3s_agent.id,
  ]

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }

  tags = {
    Name = "k3s-agent1"
    Role = "k3s-agent"
  }
}

resource "aws_instance" "k3s_agent2" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = "t3.small"
  subnet_id              = aws_subnet.public.id
  key_name               = "cle-ssh"
  iam_instance_profile   = aws_iam_instance_profile.ec2.name
  vpc_security_group_ids = [
    aws_security_group.k3s_common.id,
    aws_security_group.k3s_agent.id,
  ]

  root_block_device {
    volume_size = 8
    volume_type = "gp3"
  }

  tags = {
    Name = "k3s-agent2"
    Role = "k3s-agent"
  }
}

resource "aws_eip" "k3s_server" {
  instance   = aws_instance.k3s_server.id
  domain     = "vpc"
  depends_on = [aws_internet_gateway.main]

  tags = {
    Name = "k3s-server-eip"
  }
}
