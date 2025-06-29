output "bastion_public_ip" {
  value = aws_instance.bastion.public_ip
}

output "msk_bootstrap_brokers" {
  value = aws_msk_cluster.msk.bootstrap_brokers_sasl_iam
}
