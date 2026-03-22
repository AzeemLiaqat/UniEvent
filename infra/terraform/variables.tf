variable "project_name" {
  type        = string
  description = "Name prefix for UniEvent resources"
  default     = "unievent"
}

variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "vpc_cidr" {
  type        = string
  default     = "10.10.0.0/16"
}

variable "public_subnet_cidrs" {
  type    = list(string)
  default = ["10.10.1.0/24", "10.10.2.0/24"]
}

variable "private_subnet_cidrs" {
  type    = list(string)
  default = ["10.10.11.0/24", "10.10.12.0/24"]
}

variable "instance_type" {
  type    = string
  default = "t3.micro"
}

variable "app_repo_url" {
  type        = string
  description = "Public Git repository URL for the UniEvent app"
}

variable "ticketmaster_api_key" {
  type        = string
  sensitive   = true
  description = "Ticketmaster API key"
}
