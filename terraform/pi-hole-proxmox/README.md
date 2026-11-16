# Terraform

## Credentials

You can check the up-to-date documentation [here](https://registry.terraform.io/providers/Telmate/proxmox/latest/docs#creating-the-proxmox-user-and-role-for-terraform).

To create the user:

```bash
$ pveum role add TerraformProv -privs "Datastore.AllocateSpace Datastore.AllocateTemplate Datastore.Audit Pool.Allocate Sys.Audit Sys.Console Sys.Modify VM.Allocate VM.Audit VM.Clone VM.Config.CDROM VM.Config.Cloudinit VM.Config.CPU VM.Config.Disk VM.Config.HWType VM.Config.Memory VM.Config.Network VM.Config.Options VM.Migrate VM.Monitor VM.PowerMgmt SDN.Use"
$ pveum user add terraform-prov@pve --password <password>
$ pveum aclmod / -user terraform-prov@pve -role TerraformProv

```

Then just create an authentication token for this user.

**Datacenter → Permissions → API Tokens → Add → uncheck Privilege Separation.**

Put these credentials in a `.env` file.

```bash
export PM_API_TOKEN_ID="<token id>"
export PM_API_TOKEN_SECRET="<token secret>"
```

Then you only need to make sure these variables exist wherever you run Terraform. To use it locally, I usually do the following:

```bash
$ source .env
$ terraform init
$ terraform apply
```
