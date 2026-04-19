#!/bin/bash
#
#monta disco no /mnt
sudo chown -R antony:antony /mnt
sudo mount -t ext4 /dev/sdb /mnt/homelab-hd-filmes/
sudo mount -t ext4 /dev/sdc /mnt/homelab-hd-series/

#inicia docker depois de montar o disco
sudo systemctl start docker