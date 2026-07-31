# NIS7A

Application web NIS7A avec backend Python (auth admin, upload, stats, sessions).

## Lancer en local (recommande)

```bash
cd /Users/anismarzouk/Desktop/ANIS\ APP
python3 server.py
```

Le serveur affiche le port utilise au demarrage (ex: 8000, 8001, 8002...).

Pages utiles:
- Site public: http://127.0.0.1:PORT/
- Admin login: http://127.0.0.1:PORT/admin/login.html

Compte admin par defaut:
- Identifiant: anis
- Mot de passe: anis

## Lancer avec Docker

### Option A - Docker Compose (plus simple)

```bash
cd /Users/anismarzouk/Desktop/ANIS\ APP
docker compose up -d --build
```

Arreter:

```bash
docker compose down
```

### Option B - Docker build/run

```bash
cd /Users/anismarzouk/Desktop/ANIS\ APP
docker build -t nis7a-app .
docker run -d --name nis7a-app -p 8000:8000 \
	-e HOST=0.0.0.0 -e PORT=8000 \
	-v "$(pwd)/data:/app/data" \
	-v "$(pwd)/uploads:/app/uploads" \
	nis7a-app
```

## Rendre le repo public

1. Ouvre le repo GitHub `Anismk077/nis7a-private`.
2. Va dans Settings -> General.
3. En bas, section Danger Zone -> Change repository visibility.
4. Choisis Public et confirme.

## Publier sur nis7a.fr

GitHub Pages ne suffit pas pour cette application complete: l'admin utilise un backend Python, des sessions et des uploads. Pour publier sur `nis7a.fr`, il faut un serveur allume en permanence.

### 1. Pointer le domaine vers le serveur

Chez ton registrar DNS, cree:

- un enregistrement `A` pour `nis7a.fr` vers l'IP publique du serveur
- un enregistrement `A` pour `www.nis7a.fr` vers la meme IP

### 2. Deployer la version publique

```bash
cd /opt/nis7a
docker compose -f docker-compose.public.yml up -d --build
```

Le fichier [docker-compose.public.yml](/Users/anismarzouk/Desktop/marzoukeur/ANIS%20APP/docker-compose.public.yml) lance:

- l'application Python NIS7A
- Caddy en facade sur 80/443 avec HTTPS automatique pour `nis7a.fr`

### 3. Installation serveur complete

```bash
sudo mkdir -p /opt/nis7a
sudo chown -R "$USER":"$USER" /opt/nis7a
git clone https://github.com/Anismk077/nis7a-private.git /opt/nis7a
cd /opt/nis7a
docker compose -f docker-compose.public.yml up -d --build
```

### 4. Demarrage automatique

```bash
cd /opt/nis7a
chmod +x deploy/setup-server.sh deploy/update.sh
sudo cp deploy/systemd/nis7a.service /etc/systemd/system/nis7a.service
sudo systemctl daemon-reload
sudo systemctl enable --now nis7a.service
```

### 5. Mise a jour

```bash
cd /opt/nis7a
./deploy/update.sh
```

## Recuperer sur ton vrai PC

```bash
git clone https://github.com/Anismk077/nis7a-private.git
cd nis7a-private
docker compose up -d --build
```

Puis ouvre:
- http://127.0.0.1:8000/admin/login.html

## Mode 24/7 (meme PC eteint)

Pour que le site reste accessible quand ton PC est eteint, il faut le lancer sur un serveur allume en permanence (VPS/VM).

### Installation serveur en 5 commandes

```bash
sudo mkdir -p /opt/nis7a
sudo chown -R "$USER":"$USER" /opt/nis7a
git clone https://github.com/Anismk077/nis7a-private.git /opt/nis7a
cd /opt/nis7a
docker compose -f docker-compose.public.yml up -d --build
```

### Demarrage automatique au reboot serveur

```bash
cd /opt/nis7a
chmod +x deploy/setup-server.sh deploy/update.sh
sudo cp deploy/systemd/nis7a.service /etc/systemd/system/nis7a.service
sudo systemctl daemon-reload
sudo systemctl enable --now nis7a.service
```

### Mise a jour apres un push GitHub

```bash
cd /opt/nis7a
./deploy/update.sh
```

## Important securite

Ton token GitHub a ete expose dans l'historique terminal. Revoque-le et cree un nouveau token immediatement.
