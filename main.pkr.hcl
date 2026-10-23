locals {
  build_id   = formatdate("YYYYMMDD-hhmmss", timestamp())
  image_name = "${var.image_family}-${local.build_id}"
}

build {
  name    = "debian13-gcp"
  sources = ["source.googlecompute.debian13"]

  provisioner "ansible" {
    playbook_file = abspath(var.ansible_playbook_file)
    user          = build.User
    host_alias    = "image"
    groups        = ["packer"]

    # El proxy local reutiliza el comunicador de Packer, incluido su túnel IAP.
    use_proxy        = true
    sftp_command     = "/usr/lib/openssh/sftp-server -e"
    ansible_env_vars = ["ANSIBLE_PIPELINING=False"]
    extra_arguments = concat(
      ["--become", "--extra-vars", "ansible_python_interpreter=/usr/bin/python3"],
      var.ansible_extra_arguments
    )
  }

  # Comprueba el arranque después de actualizar el kernel y los paquetes.
  provisioner "shell" {
    inline            = ["sudo -n systemctl reboot"]
    expect_disconnect = true
  }

  provisioner "ansible" {
    pause_before  = "30s"
    playbook_file = "${path.root}/ansible/playbooks/finalize.yml"
    user          = build.User
    host_alias    = "image"
    groups        = ["packer"]

    use_proxy        = true
    sftp_command     = "/usr/lib/openssh/sftp-server -e"
    ansible_env_vars = ["ANSIBLE_PIPELINING=False"]
    # Los argumentos personalizados solo se aplican al playbook de paquetes.
    extra_arguments = ["--become", "--extra-vars", "ansible_python_interpreter=/usr/bin/python3"]
  }

  post-processor "manifest" {
    output = "${path.root}/manifest.json"
    custom_data = {
      image_name   = local.image_name
      image_family = var.image_family
      os           = "debian-13-amd64"
      playbook     = var.ansible_playbook_file
    }
  }
}
