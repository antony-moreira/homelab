resource "local_file" "ansible_inventory" {
  content = templatefile("inventory.tmpl",
    {
      portainer = {
        index      = range(local.portainer.count)
        ip_address = proxmox_vm_qemu.portainer.*.default_ipv4_address
        user       = proxmox_vm_qemu.portainer.*.ciuser
        vm_name    = proxmox_vm_qemu.portainer.*.name
      }
    }    
  )
  filename        = "inventory.ini"
  file_permission = "0600"
}


