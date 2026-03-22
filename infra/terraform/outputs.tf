output "alb_dns_name" {
  value       = aws_lb.unievent_alb.dns_name
  description = "Open this DNS name in the browser to access UniEvent"
}

output "events_bucket_name" {
  value = aws_s3_bucket.events_bucket.id
}

output "asg_name" {
  value = aws_autoscaling_group.unievent_asg.name
}
