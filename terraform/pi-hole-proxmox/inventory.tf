resource "local_file" "ansible_inventory" {
  content = templatefile("inventory.tmpl",
    {
      app = {
        index      = range(local.apps.count)
        ip_address = proxmox_vm_qemu.apps.*.default_ipv4_address
        user       = proxmox_vm_qemu.apps.*.ciuser
        vm_name    = proxmox_vm_qemu.apps.*.name
      }
    }    
  )
  filename        = "inventory.ini"
  file_permission = "0600"
}


