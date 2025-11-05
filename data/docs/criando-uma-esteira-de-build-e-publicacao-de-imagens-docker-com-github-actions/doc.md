---
access_level: d1
category: d2
created_at: 2025-10-30 13:53:53 UTC-03:00
created_by: admin
description: ''
icon_url: /docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/logo-2-c6319b.png
last_edited_at: 2025-10-30 13:59:11 UTC-03:00
last_edited_by: admin
tags:
- docker
title: Criando uma esteira de build e publicação de imagens Docker com GitHub Actions
---

Este guia ensina como configurar uma <b>pipeline automatizada</b> no GitHub para gerar e publicar imagens Docker automaticamente no <b>Docker Hub</b> (ou outro registro de sua preferência) sempre que houver um push no repositório.

# Repositório da aplicação

[esteira-docker](https://github.com/SeaBirdsCloud/esteira-docker)

Crie um repositório Git contendo os mesmos arquivos do repositório de exemplo.

<u><b>Importante</b>: o arquivo Dockerfile deve estar na raiz do repositório.</u>

A estrutura deve se parecer com a seguinte:


![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-2c6653.png)

# Criando o Workflow do GitHub Actions

Dentro do seu repositório, crie o arquivo:

```
.github/workflows/docker-build.yml
```

E adicione o seguinte conteúdo:

```
name: Build and Push Docker Image

on:
  push:
    branches:
      - main  # ou o nome da branch que você usa

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout do código
        uses: actions/checkout@v4

      - name: Login no Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKERHUB_USERNAME }}
          password: ${{ secrets.DOCKERHUB_TOKEN }}

      - name: Build e Push da imagem
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ secrets.DOCKERHUB_USERNAME }}/quiz-divertido:latest
```

Exemplo:

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-872fad.png)

# Configurando Credenciais do Docker Hub

Acesse o menu do repositório no GitHub:

<b>Settings → Secrets and variables → Actions</b>

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-218973.png)

Clique em “`New repository secret`”

Crie as seguintes variáveis:

<!-- TABELA:INICIO -->
| Campo | Valor |
|---|---|
| DOCKERHUB_USERNAME | Seu nome de usuário do Docker Hub |
| DOCKERHUB_TOKEN | Token de acesso (crie em Docker Hub → Account Settings → Personal Access Tokens → New Token) |
<!-- TABELA:FIM -->

Deve ficar dessa forma:

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-5b87f0.png)

# Testando o Workflow

Faça uma pequena modificação no arquivo <b>index.html</b>, como alterar o <b>title</b> da página.

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-448b56.png)

Faça <b>commit</b> e <b>push</b> para a branch monitorada (main, por exemplo).

Vá até a aba <b>Actions</b> no GitHub e veja o pipeline em execução.

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-079362.png)

Ela carregou tadas as etapas:

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-fa7c71.png)

Quando o processo terminar, a nova imagem será publicada no seu repositório Docker Hub.

# Testando Localmente a Imagem

Execute o comando abaixo para rodar a imagem mais recente:

```
docker run -p 80:3000 -d <NOME-DO-SEU-USER>/<NOME-DA-SUA-IMG>:latest
```

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-f22611.png)

Verifique os containers em execução:

```
docker ps
```

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-a72b6a.png)

Acesse no navegador:

[localhost](http://localhost/)

Você verá a aplicação em funcionamento com a nova imagem.

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-6de214.png)

# Atualizando a Aplicação

Edite o arquivo <b>/src/App.jsx</b> e altere a linha:

```
<h1 className="text-2xl md:text-3xl font-bold tracking-tight">Quiz Divertido</h1>
```

Para:

```
<h1 className="text-2xl md:text-3xl font-bold tracking-tight">Quiz Divertido - Perdix</h1>
```

Faça <b>commit</b> e <b>push</b> novamente.

O GitHub Actions iniciará automaticamente um novo <b>job</b>.

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-1cd94b.png)

Após a conclusão, atualize o container local:

Para visualizar os containers em execução

```
docker ps
```

Exclua o container atual:

```
docker rm <ID-CONTAINER> -f
```

Exclua a imagem do container atual:

```
docker rmi <NOME-DO-SEU-USER>/<NOME-DA-SUA-IMG>
```

Execute para criar a container novamente (isso faz com que ele baixe a imagem caso ela não exista na sua máquina):

```
docker run -p 80:3000 -d <NOME-DO-SEU-USER>/<NOME-DA-SUA-IMG>:latest
```

Acesse novamente:

[localhost](http://localhost/)

E confira o novo título atualizado.

![image.png](/docs/criando-uma-esteira-de-build-e-publicacao-de-imagens-docker-com-github-actions/image-95a8e6.png)

# Conclusão

Com essa configuração, você automatiza todo o processo de build e publicação de imagens Docker — garantindo que toda alteração no código resulte em uma imagem atualizada no Docker Hub, pronta para uso ou deploy.