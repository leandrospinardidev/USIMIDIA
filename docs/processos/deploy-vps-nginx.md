# Deploy em VPS com Docker Compose + Nginx

Este guia cobre um deploy simples e reproduzivel para o ERP Industrial:

- **web** (React buildado e servido por Nginx em container),
- **api** (FastAPI em container),
- **db** (PostgreSQL em container),
- **Nginx do host** fazendo TLS (HTTPS) e reverse proxy.

## 1) Pre-requisitos no servidor

- Ubuntu 22.04+ (ou distro equivalente)
- Docker + Docker Compose Plugin
- Nginx
- Certbot (para LetsEncrypt)
- Git

Exemplo (Ubuntu):

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin nginx certbot python3-certbot-nginx git
sudo systemctl enable --now docker nginx
```

## 2) Obter o projeto e configurar variaveis

```bash
git clone <URL_DO_REPOSITORIO> /srv/erp-industrial
cd /srv/erp-industrial
```

Crie o arquivo de ambiente de producao:

```bash
cd infra/docker
cp env.prod.example .env.prod
```

Edite `.env.prod` e ajuste principalmente:

- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `CORS_ALLOWED_ORIGINS` (dominio publico do front)
- `WEB_PORT` (padrao `8080`, somente loopback)

## 3) Subir stack de producao

No diretorio `infra/docker`:

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build db api web
```

### Rodar migrations

Use o servico `migrator` (perfil `ops`):

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile ops run --rm migrator
```

> O `migrator` ja possui retry interno. Em ambientes onde o healthcheck do Postgres oscila,
> a aplicacao nao fica travada: `api`/`web` sobem e o `migrator` tenta aplicar as migrations
> algumas vezes ate o banco aceitar conexao.

## 4) Testes de smoke (antes do dominio)

Ainda no servidor:

```bash
curl http://127.0.0.1:8080/healthz
curl http://127.0.0.1:8080/health
curl -H "X-User-Role: admin" "http://127.0.0.1:8080/api/v1/ordens-producao?page=1&page_size=1"
```

Esperado:

- `/healthz` -> `ok` (web/nginx container)
- `/health` -> `{"status":"ok"}` (api)
- endpoint da API responde JSON (mesmo que lista vazia)

## 5) Configurar Nginx do host (dominio + HTTPS)

Arquivo de exemplo:

- `infra/nginx/erp-industrial.conf.example`

Instale no host:

```bash
sudo cp /srv/erp-industrial/infra/nginx/erp-industrial.conf.example /etc/nginx/sites-available/erp-industrial.conf
sudo nano /etc/nginx/sites-available/erp-industrial.conf
sudo ln -sf /etc/nginx/sites-available/erp-industrial.conf /etc/nginx/sites-enabled/erp-industrial.conf
sudo nginx -t
sudo systemctl reload nginx
```

Substitua:

- `server_name erp.seudominio.com`
- caminhos de certificado em `/etc/letsencrypt/live/...`

Gerar certificado (LetsEncrypt):

```bash
sudo certbot --nginx -d erp.seudominio.com
```

Depois:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 6) Fluxo de atualizacao (deploy continuo manual)

```bash
cd /srv/erp-industrial
git pull
cd infra/docker
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d --build api web
docker compose --env-file .env.prod -f docker-compose.prod.yml --profile ops run --rm migrator
```

## 7) Logs e diagnostico

```bash
cd /srv/erp-industrial/infra/docker
docker compose --env-file .env.prod -f docker-compose.prod.yml ps
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f api
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f web
docker compose --env-file .env.prod -f docker-compose.prod.yml logs -f db
```

## 8) CORS e dominios

O backend agora tem CORS habilitado via `CORS_ALLOWED_ORIGINS`.

- Em **mesmo dominio** (recomendado), mantenha o proxy do Nginx do host e um unico dominio.
- Em **dominios separados**, ajuste `CORS_ALLOWED_ORIGINS` para o dominio exato do frontend (ou lista separada por virgula).

