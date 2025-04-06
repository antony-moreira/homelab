#!/bin/bash
#
#monta disco no /mnt
sudo chown -R ubuntu:ubuntu /mnt/*
sudo mount -t ext4 /dev/sdb /mnt/homelab-ssd-thor/
sudo mount -t ext4 /dev/sdc /mnt/homelab-hd-externo-thor/

#inicia docker depois de montar o disco
sudo systemctl start docker