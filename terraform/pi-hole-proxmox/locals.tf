locals {
  # global configurations
  agent        = 1
  cidr         = "192.168.3.0/24"
  onboot       = true
  proxmox_node = "ebony"
  scsihw       = "virtio-scsi-pci"
  template     = "ubuntu-2404-cloud-init"

  bridge = {
    interface = "vmbr0"
    model     = "virtio"
  }
  disks = {
    main = {
      backup  = true
      format  = "raw"
      type    = "disk"
      storage = "local-lvm"
      slot    = "scsi0"
    }
    cloudinit = {
      backup  = false
      format  = "raw"
      type    = "cloudinit"
      storage = "local-lvm"
      slot    = "ide2"
    }
  }
  # serial is needed to connect via WebGUI console
  serial = {
    id   = 0
    type = "socket"
  }

  # cloud init information to be injected
  cloud_init = {
    user           = "ubuntu"
    password       = "ubuntu"
    ssh_public_key = file("/Users/antony/.ssh/id_rsa.pub")
  }


  apps = {
    count = 1

    name_prefix = "pi-hole"
    vmid_prefix = 100

    cores     = 1
    disk_size = "50G"
    memory    = 512
    sockets   = 1

    network_last_octect = 100
    tags                = "pi-hole"
  }
}
