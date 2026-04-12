#!/bin/bash
#
#monta disco no /mnt
sudo chown -R ubuntu:ubuntu /mnt/*
sudo mount -t ext4 /dev/sdb /mnt/homelab-hd-interno/
sudo mount -t ext4 /dev/sdc /mnt/homelab-hd-externo/

#inicia docker depois de montar o disco
sudo systemctl start docker