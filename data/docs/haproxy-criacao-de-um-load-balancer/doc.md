---
access_level: d1
category: d2
created_at: 2025-10-29 15:03:23 UTC-03:00
created_by: Lucas
description: ''
icon_url: /docs/haproxy-criacao-de-um-load-balancer/logo-1-72d6ca.png
last_edited_at: 2025-10-29 15:04:53 UTC-03:00
last_edited_by: Lucas
tags:
- Demo
title: 'HAProxy: Criação de um Load Balancer'
---

# O que é o HAProxy
O **HAProxy (High Availability Proxy)** é um software livre e de código aberto que atua como um balanceador de carga e servidor proxy para aplicações baseadas em **TCP** e **HTTP**, distribuindo o tráfego entre múltiplos servidores. Ele é amplamente utilizado por sua **velocidade**, **eficiência** e **robustez**, garantindo **alta disponibilidade**, **melhor desempenho** e **gestão inteligente de tráfego web**.

# Criação do ambiente
Neste laboratório, criaremos três máquinas virtuais utilizando o Vagrant:

* 1 máquina com HAProxy
* 2 máquinas com Apache

`Arquivo Vagrantfile`

```
Vagrant.configure("2") do |config|
    (1..1).each do |i|
        config.vm.define "haproxy" do |haproxy|
            haproxy.vm.box = "ubuntu/jammy64"
            haproxy.vm.hostname = "haproxy"
            haproxy.vm.network "public_network", bridge: "default"
            haproxy.ssh.insert_key = false
            haproxy.vm.provision "shell", path: "script.sh"

            haproxy.vm.provider "virtualbox" do |vb|
            vb.gui = true
            vb.cpus = 2
            vb.memory = "2048"
            end
        end
    end

    (1..2).each do |i|
        config.vm.define "apache-#{i}" do |apache|
            apache.vm.box = "ubuntu/jammy64"
            apache.vm.hostname = "apache-#{i}"
            apache.vm.network "public_network", bridge: "default"
            apache.ssh.insert_key = false
            apache.vm.provision "shell", path: "script.sh"
            apache.vm.provision "shell", path: "apache.sh"

            apache.vm.provider "virtualbox" do |vb|
            vb.gui = true
            vb.cpus = 2
            vb.memory = "2048"
            end
        end
    end
end
```

`Arquivo script.sh`

Script de inicialização das instâncias, configurando senha do root, acesso SSH e rede.


```
#!/usr/bin/env bash
set -euo pipefail

# ======== CONFIGURAÇÃO ========
USER="root"
ROOT_SENHA="123456"
# ===============================

echo "==> Alterando senha do usuário root..."
echo "${USER}:${ROOT_SENHA}" | sudo chpasswd
echo "Senha de root alterada com sucesso!"

echo "==> Habilitando login SSH como root..."
sudo sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config.d/60-cloudimg-settings.conf
sudo sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config
sudo systemctl restart ssh || sudo service ssh restart || true
echo "SSH configurado e reiniciado."

echo "==> Detectando interfaces IPv4 (ignorando loopback, link-local e NAT 10.0.2.x)..."

BRIDGE_IFACE=""
BRIDGE_IP=""
GATEWAY=""

# 1) Detecta via `ip`, ignorando IPs inválidos
while read -r iface addr; do
  ip_only=${addr%%/*}
  if [[ "$ip_only" == 127.* ]] || [[ "$ip_only" == 169.254.* ]] || [[ "$ip_only" == 10.0.2.* ]]; then
    continue
  fi
  BRIDGE_IFACE=$iface
  BRIDGE_IP=$ip_only
  break
done < <(ip -4 -o addr show scope global | awk '{print $2, $4}')

# 2) Tenta via nmcli, se necessário
if [ -z "$BRIDGE_IFACE" ] && command -v nmcli >/dev/null 2>&1; then
  echo "==> Tentando detecção com nmcli..."
  for dev in $(nmcli -t -f DEVICE,STATE,TYPE device status | awk -F: '$2=="connected" && ($3=="ethernet"||$3=="wifi"){print $1}'); do
    ipaddr=$(nmcli -g IP4.ADDRESS device show "$dev" | head -n1 | cut -d/ -f1)
    if [ -z "$ipaddr" ]; then continue; fi
    if [[ "$ipaddr" == 127.* ]] || [[ "$ipaddr" == 169.254.* ]] || [[ "$ipaddr" == 10.0.2.* ]]; then
      continue
    fi
    BRIDGE_IFACE=$dev
    BRIDGE_IP=$ipaddr
    GATEWAY=$(nmcli -g IP4.GATEWAY device show "$dev" | head -n1)
    break
  done
fi

# 3) Obtém gateway se faltando
if [ -n "$BRIDGE_IFACE" ] && [ -z "$GATEWAY" ]; then
  GATEWAY=$(ip route show dev "$BRIDGE_IFACE" | awk '/default/ {print $3; exit}' || true)
  if [ -z "$GATEWAY" ]; then
    GATEWAY=$(ip route | awk -v ip="$BRIDGE_IP" 'match($0,ip){for(i=1;i<=NF;i++) if($i=="via") print $(i+1)}' | head -n1 || true)
  fi
fi

# 4) Ajusta rota padrão
if [ -n "$BRIDGE_IFACE" ]; then
  echo "==> Interface candidata: $BRIDGE_IFACE ($BRIDGE_IP)"
  if [ -n "$GATEWAY" ]; then
    echo "==> Ajustando rota padrão para via $GATEWAY dev $BRIDGE_IFACE"
    sudo ip route del default || true
    sudo ip route add default via "$GATEWAY" dev "$BRIDGE_IFACE"
    echo "Rota padrão ajustada para interface $BRIDGE_IFACE ($GATEWAY)"
  else
    echo "⚠️  Interface $BRIDGE_IFACE detectada, mas não consegui determinar o gateway. Rota não alterada."
  fi
else
  echo "⚠️  Nenhuma interface 'bridge' detectada (fora da NAT 10.0.2.x)."
  echo "    Verifique se o modo de rede da VM está configurado corretamente."
fi

# Exibe estado final
echo ""
echo "=============================="
echo " Configuração concluída!"
echo " Usuário SSH : $USER"
echo " Nova senha  : $ROOT_SENHA"
echo " Endereço IP : $BRIDGE_IP"
echo "=============================="
```

Este script também detecta automaticamente a interface de rede “bridge” e ajusta a rota padrão.

`Arquivo apache.sh`

Instala e configura o Apache com uma página HTML personalizada que exibe o **hostname** da máquina.


```
#!/usr/bin/env bash
set -euo pipefail

# script: setup-apache.sh
# objetivo: instalar apache e criar uma página estilizada com o hostname

# Confere se está rodando como root; se não, tenta usar sudo
if [ "$EUID" -ne 0 ]; then
  echo "Executando com sudo..."
  exec sudo bash "$0" "$@"
fi

echo "Detectando distribuição..."
if command -v apt-get >/dev/null 2>&1; then
  PM="apt"
  INSTALL="apt-get update -y && apt-get install -y apache2"
  SERVICE_NAME="apache2"
  WWW_DIR="/var/www/html"
elif command -v dnf >/dev/null 2>&1; then
  PM="dnf"
  INSTALL="dnf install -y httpd"
  SERVICE_NAME="httpd"
  WWW_DIR="/var/www/html"
elif command -v yum >/dev/null 2>&1; then
  PM="yum"
  INSTALL="yum install -y httpd"
  SERVICE_NAME="httpd"
  WWW_DIR="/var/www/html"
else
  echo "Gerenciador de pacotes não suportado automaticamente neste script."
  exit 1
fi

echo "Gerenciador detectado: $PM"
echo "Instalando pacotes necessários..."
eval "$INSTALL"

echo "Habilitando e iniciando o serviço $SERVICE_NAME..."
if command -v systemctl >/dev/null 2>&1; then
  systemctl enable "$SERVICE_NAME"
  systemctl restart "$SERVICE_NAME"
else
  if command -v service >/dev/null 2>&1; then
    service "$SERVICE_NAME" restart || true
  fi
fi


# Obter hostname
HOSTNAME=$(hostname --fqdn 2>/dev/null || hostname)

# Criar página
INDEX_FILE="$WWW_DIR/index.html"
BACKUP="$INDEX_FILE.bak.$(date +%Y%m%d%H%M%S)"

if [ -f "$INDEX_FILE" ]; then
  echo "Fazendo backup do index atual em $BACKUP"
  cp "$INDEX_FILE" "$BACKUP"
fi

cat > "$INDEX_FILE" <<HTML
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>$HOSTNAME</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
        /* Reset básico */
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }

        body {
            display: flex;
            flex-direction: column;
            min-height: 100vh;
            justify-content: center;
            align-items: center;
            background: #f0f2f5;
            color: #333;
            padding: 20px;
        }

        .card {
            background: #fff;
            border-radius: 16px;
            box-shadow: 0 8px 20px rgba(0, 0, 0, 0.1);
            padding: 40px 30px;
            text-align: center;
            max-width: 350px;
            width: 100%;
            transition: transform 0.2s, box-shadow 0.2s;
        }

        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 12px 24px rgba(0, 0, 0, 0.15);
        }

        .emoji {
            font-size: 60px;
            margin-bottom: 20px;
        }

        h1 {
            font-size: 1.8rem;
            margin-bottom: 10px;
            color: #0077cc;
            word-break: break-word;
        }

        p {
            font-size: 1rem;
            color: #666;
        }

        footer {
            margin-top: 40px;
            font-size: 0.85rem;
            color: #999;
            text-align: center;
        }

        @media (max-width: 400px) {
            .card {
                padding: 30px 20px;
            }

            .emoji {
                font-size: 50px;
            }

            h1 {
                font-size: 1.5rem;
            }
        }
    </style>
</head>
<body>
    <div class="card">
        <div class="emoji">🐦</div>
        <h1>$HOSTNAME</h1>
        <p>Instância em execução</p>
    </div>
    <footer>Gerado automaticamente em $(date -u +"%Y-%m-%d %H:%M:%SZ") (UTC)</footer>
</body>

</html>
HTML

echo "Página criada em: $INDEX_FILE"
chown -R www-data:www-data "$WWW_DIR" 2>/dev/null || true
chmod -R 755 "$WWW_DIR" 2>/dev/null || true
```

Crie o ambiente com o comando:

```
vagrant up
```

Após a criação das VMs, você poderá acessar as páginas individuais dos servidores Apache pelo IP informado na saída do vagrant up.

Exemplo:


![image.png](/docs/haproxy-criacao-de-um-load-balancer/image-a1b909.png)

# Instalando o HAProxy

Acesse a instância via SSH e siga os processos.

Atualize o sistema e instale o HAProxy:


```
sudo apt update
sudo apt install haproxy -y
```

Edite o arquivo de configuração:

```
sudo nano /etc/haproxy/haproxy.cfg
```

Veja o arquivo de configuração:

![image.png](/docs/haproxy-criacao-de-um-load-balancer/image-f020ff.png)

## Exemplo de configuração

```
frontend perdix-apache
        mode http
        bind :80
        default_backend myapp

backend myapp
        server apache1 10.34.5.29:80
        server apache2 10.34.5.215:80
```

Substitua os IPs acima pelos IPs reais das suas instâncias Apache.

Ela deve ficar parecida da seguinte forma:

![image.png](/docs/haproxy-criacao-de-um-load-balancer/image-502683.png)

Após salvar, recarregue o serviço:

```
sudo systemctl restart haproxy
```

Acesse o IP da instância do HAProxy pelo navegador — o balanceamento deve alternar entre as páginas dos servidores apache-1 e apache-2.

#### Apache-1

![image.png](/docs/haproxy-criacao-de-um-load-balancer/image-284ddd.png)

#### Apache-2

![image.png](/docs/haproxy-criacao-de-um-load-balancer/image-3ab165.png)

# Habilitando a página de status (métricas HTTP)
Para expor métricas via HTTP, adicione ao final do arquivo /etc/haproxy/haproxy.cfg:

```
listen stats # Define a listen section called "stats"
        bind :9000 # Listen on port 9000
        mode http
        stats enable  # Enable stats page
        stats hide-version  # Hide HAProxy version
        stats realm Haproxy\ Statistics  # Title text for popup window
        stats uri /haproxy_stats  # Stats URI
        stats refresh 5s
        stats show-legends
        stats show-node
```

Opcionalmente, adicione autenticação básica:

```
stats auth usuario:senha
```

Acesse via navegador:

```
http://<IP-DO-HAPROXY>:9000/haproxy_stats
```

O resultado deve ser parecido:

![image.png](/docs/haproxy-criacao-de-um-load-balancer/image-adc630.png)

# Habilitando o soquete UNIX

Adicione na seção global do haproxy.cfg:

```
global
    stats socket /run/haproxy/haproxy.sock mode 660 level admin
```

Recarregue o serviço:

```
sudo systemctl reload haproxy
```

Verifique se o socket foi criado:

```
ls -l /run/haproxy/haproxy.sock
```

Instale o socat e visualize métricas:

```
sudo apt install socat -y
printf "show stat\n" | socat - UNIX-CONNECT:/run/haproxy/haproxy.sock
```

# Métricas importantes do HAProxy

## Frontend

Representam o tráfego **de entrada** no HAProxy.

<!-- TABELA:INICIO -->
| Métrica | Descrição |
|---|---|
| scur | Conexões ativas |
| smax | Pico de conexões simultâneas |
| stot | Total de conexões aceitas |
| ereq | Requisições inválidas |
| bin / bout | 	Bytes recebidos/enviados |
| dreq / dresp | Requisições/respostas descartadas |
<!-- TABELA:FIM -->


## Backend

Refletem a **saúde** e o **desempenho** dos servidores de aplicação.

| Métrica |	Descrição |
|-|-|
| status |	Estado do servidor (UP/DOWN/MAINT)|
| qcur / qmax	 | Fila atual / máxima|
| scur / smax / stot |	Sessões ativas, pico e total|
| hrsp_2xx, hrsp_4xx, hrsp_5xx | Respostas HTTP por código|
| econ, eresp	| Conexões e respostas com erro |
| rtime, ttime	| Tempo médio de resposta |

## Sistema / Global

Informações gerais sobre o funcionamento do balanceador.

<!-- TABELA:INICIO -->
| Métrica | Descrição |
|---|---|
| uptime_sec | 	Tempo de execução |
| curr_conns / maxconn | Conexões atuais / limite |
| cum_conns | Total de conexões desde o início |
| bytes_in / bytes_out | Tráfego total |
| conn_rate / conn_rate_max | Taxa de novas conexões |
| tasks / run_queue | 	Tarefas e threads ativas |
<!-- TABELA:FIM -->

# Conclusão

Com o ambiente configurado, o HAProxy distribui o tráfego entre múltiplos servidores Apache, garantindo **alta disponibilidade**, **resiliência** e **balanceamento eficiente**.

A interface de métricas facilita o **monitoramento** de desempenho e **análise de carga**, tornando o sistema mais confiável e escalável.