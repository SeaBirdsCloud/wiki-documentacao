---
access_level: d1
category: d1
created_at: 2025-10-30 14:04:00 UTC-03:00
created_by: admin
description: ''
icon_url: /docs/loja-de-acai-documentacao-de-rede/img-0-1-70689d.png
last_edited_at: 2025-10-30 14:04:37 UTC-03:00
last_edited_by: admin
tags:
- Redes de Computadores
title: Loja de Açaí – Documentação de Rede
---

# 1. Objetivo

Este ambiente simula a infraestrutura de rede de uma loja de açaí, com foco em conectividade local (LAN) e acesso à internet, além da configuração de serviços básicos como DHCP, DNS e Web.

# 2. Topologia da Rede

A topologia consiste em uma rede LAN conectada a uma rede pública por meio de um roteador sem fio. A comunicação entre os dispositivos locais é feita por um switch central, e o acesso externo ocorre via NAT no roteador.

![image.png](/docs/loja-de-acai-documentacao-de-rede/image-7b53f2.png)

# 3. Dispositivos Utilizados

* <b>Roteador</b> - Modelo: WRT300N; Quantidade: 1
* <b>Switch</b> - Modelo: 2960-24TT; Quantidade: 1
* <b>Tablet</b> - Modelo: tabletPC-PT; Quantidade: 2
* <b>Computadores (PC)</b> - Modelo: PC-PT; Quantidade: 3
* <b>Servidor</b> - Modelo: Server-PT; Quantidade: 1

# 4. Endereçamento IP

A maioria dos dispositivos utiliza endereçamento dinâmico (DHCP), com exceção do servidor, que possui IP estático para funcionamento correto dos serviços DNS e Web.

* <b>Servidor</b> - IP: 192.168.0.104; Máscara: 255.255.255.0; Gateway: 192.168.0.1; Tipo: Estático
* <b>Demais Dispositivos</b> - IP: Atribuído via DHCP; Máscara: 255.255.255.0; Gateway: 192.168.0.1; Tipo: Dinâmico

# 5. Configuração de VLANs

Não aplicável neste ambiente.

Caso deseje implementar VLANs no futuro, pode-se separar funções administrativas, clientes e serviços em diferentes domínios de broadcast.

# 6. Serviços Configurados

* <b>DHCP</b> - Responsável: Roteador WRT300N; Observações: Distribui IPs automaticamente na rede local.
* <b>DNS</b> - Responsável: Servidor; Observações: Resolve nomes de domínio internos.
* <b>Web</b> - Responsável: Servidor; Observações: Hospeda uma página institucional/local.

# 7. Roteamento

O roteador faz a conexão entre a rede LAN e a internet simulada.

O servidor possui IP fixo para garantir a disponibilidade dos serviços DNS e Web.

Demais dispositivos utilizam endereçamento automático via DHCP.

# 8. Testes Realizados

![image.png](/docs/loja-de-acai-documentacao-de-rede/image-bf2c9c.png)

Ping entre todos os dispositivos para verificar conectividade.

![image.png](/docs/loja-de-acai-documentacao-de-rede/image-cd6450.png)

Acesso ao servidor Web pelo navegador dos PCs/Tablets.

![image.png](/docs/loja-de-acai-documentacao-de-rede/image-6a5b72.png)

Resolução de nomes via servidor DNS.

# 9. Observações

A simplicidade do ambiente permite fácil expansão com VLANs, controle de acesso ou serviços adicionais.

O roteador usado é doméstico (WRT300N), adequado para o porte da loja, mas pode ser substituído em ambientes mais exigentes.

O servidor centraliza os serviços e é essencial para a operação local da rede.