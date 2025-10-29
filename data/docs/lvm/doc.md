---
access_level: d1
category: d1
created_at: 2025-10-29 14:48:39 UTC-03:00
created_by: fabio
description: Como expandir um disco em formato LVM
icon_url: /docs/lvm/485126179-1059829039501718-5554138553775875433-n-fcc09c.jpg
last_edited_at: 2025-10-29 15:57:37 UTC-03:00
last_edited_by: Lucas
tags: []
title: LVM
---

# Expandir disco em LVM

Essa á uma atividade muito comum no meu dia a dia, então vou mostra como eu faço.

Problema : falta de espaço em disco

Sempre que houver expectativa de crescimento de dados crie discos com LVM assim é possível uma expansão de disco a quente sem causar indisponibilidade o serviço.

## Passo 01: 

Adicionar um disco a maquina que deseja fazer upgrade de disco

para saber quais os discos vc pode usar o comando `lsblk`

o resultado dele como exemplo:

```
sdd 8:48 0 200G 0 disk
└─sdd1 8:49 0 200G 0 part
└─VG_PGSQL-LV_DATA 253:2 0 300G 0 lvm /usr/local/pgsql
sde 8:64 0 15G 0 disk
└─sde1 8:65 0 15G 0 part
└─VG_OS-LV_Var 253:0 0 31.3G 0 lvm /var
sdf 8:80 0 15G 0 disk
└─sdf1 8:81 0 15G 0 part
└─VG_OS-LV_Var 253:0 0 31.3G 0 lvm /var
```

Supondo que vc tenha adicionado mais um disco com esse comando ele iria aparecer mais um disco com a seguinte nomeclatura sdg

## Passo02:

Então agora precisamos criar uma partição do tipo lvm usando o fdisk

```
fdisk /dev/sdg
```

opção `n` para criar uma nova partição

opção `t` com tipo 8e Linux LVM

opção `w` para escrever as alterações no disco

Criado a partição é hora de criar lvm e aqui vale ressaltar alguns detalhes, para criar ou expandir um LVM precisa ter a visão que ele tem um PV VG LV e Filesystem, ou seja precisa adicionar esse disco a um PV depois expandir ou criar o VG e depois expandir ou criar um LV.

## Passo03

Então seguindo no exemplo vamos criar o PV: pvcreate /dev/sdg1

Agora vamos expandir o nosso VG: vgextend VG_OS /dev/sdg1 (Note que /dev/sdg1 é disco que criamos VG_OS é nosso VG).

## Passo 04

Próximo passo agora é expandir LV que por sua vez faz referência a um file system, nesse caso eu poderia usar parte do espaço livre ou tudo, eu gosto de usar todo espaço livre então o comando é : lvextend -l +100%FREE /dev/VG_OS/LV_Var

Ultimo passo agora é expandir seu filesystem e isso vc pode verificar no fstab aonde tem tabela de partição com especificação do filesystem, poderia ser ext4 ou xfs por exemplo, e para cada um temos o comando de expansão:

para xfs temos: xfs_growfs /var

para ext4: resize2fs /dev/mapper/nome_lv

Essa é a forma que mais tenho utilizado no meu dia a dia sem causar indisponibilidade no serviço.

Contras sobre LVM quanto maior a quantidade disco mais você aumenta o numero de falhas uma vez que ele não faz um controle paridade como uma solução de RAID, em caso de falha de um disco vc pode comprometer seu ambiente.