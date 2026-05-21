terraform {
  required_version = ">= 1.7"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  backend "s3" {
    bucket = "deploytracker-tfstate-378202225330"
    key    = "deploytracker/terraform.tfstate"
    region = "eu-west-3"
  }
}

provider "aws" {
  region = "eu-west-3"
  default_tags {
    tags = {
      Project     = "deploytracker"
      Environment = "demo"
      ManagedBy   = "terraform"
    }
  }
}
