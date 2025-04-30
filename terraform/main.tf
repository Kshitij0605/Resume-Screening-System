provider "aws" {
  region = "us-east-1"
}

resource "aws_instance" "resume_app" {
  ami           = " "  # Amazon Linux 2 (change as needed)
  instance_type = "t2.micro"

  key_name = "your key name"

  tags = {
    Name = "ResumeAppServer"
  }

  provisioner "local-exec" {
    command = "echo ${self.public_ip} > inventory.ini"
  }
}
