# Agent LinkedIn — Quantum Consulting

Agent autonome qui redige, illustre et publie trois publications LinkedIn par semaine,
a la voix et a la direction artistique de Quantum Consulting.

Cout recurrent : GitHub Actions gratuit, Telegram gratuit, LinkedIn gratuit.
La redaction tourne sur Gemini Flash en palier gratuit, donc **0 euro par mois**.
La bascule vers Claude se fait par une variable, pour 0,30 a 1 euro par mois si
la plume de Gemini ne suffit pas.

---

## Comment ca tourne

| Quand | Ce qui se passe |
|---|---|
| Chaque matin | `veille.py` remplit la banque d'angles depuis des flux RSS gratuits |
| Dimanche soir | `generate.py` pioche des angles, redige, se relit, remplit la file |
| Toutes les 2 h, 6 h a 20 h | `review.py` releve tes reponses Telegram et tes notes de terrain |
| Mardi, mercredi, jeudi 8 h 15 | `publish.py` fabrique le visuel et publie |
| Lundi matin | `check_token.py` verifie le jeton LinkedIn |

Cinq workflows : `veille.yml`, `generate.yml`, `review.yml`, `publish.yml`, `token.yml`.

**Validation humaine systematique.** Aucune publication ne part sans ton clic.
Chaque brouillon arrive dans Telegram en deux messages : le visuel rendu en
1200x1200, puis le texte avec trois boutons.

| Bouton | Effet |
|---|---|
| Valide | part au prochain creneau de publication, et alimente le corpus |
| Modifier | le bot attend ta consigne, puis renvoie une version revue |
| Refuse | la publication est ecartee definitivement |

Apres **Modifier**, ton message suivant est interprete comme la consigne. Une
phrase courte est appliquee par le modele ; un texte de plus de 250 caracteres
est pris tel quel comme remplacement integral. Dans les deux cas le visuel est
refait pour rester coherent, et le brouillon revient avec ses trois boutons.

La variable `AUTO_PUBLISH=1` rouvrirait un mode mixte ou les piliers surs
partiraient seuls. Elle est desactivee, et c'est volontaire.

---

## Mise en service, dans l'ordre

### 1. Le depot
```sh
cd "agent-linkedin"
git init && git add . && git commit -m "agent linkedin"
gh repo create quantum-agent-linkedin --private --source=. --push
```
Mets le depot en **prive** : la file de contenus contient tes brouillons.

### 2. L'application LinkedIn
1. https://developer.linkedin.com/ → Create app, rattachee a ta page Quantum Consulting
2. Onglet **Products** → demander **Share on LinkedIn** et **Sign In with LinkedIn using OpenID Connect** (acces immediat, gratuit)
3. Onglet **Auth** → ajouter l'URL de redirection : `http://localhost:8723/callback`
4. Noter le Client ID et le Client Secret

En parallele, si tu veux la page entreprise plus tard, demande des maintenant
**Community Management API** dans Products : la validation prend 1 a 4 semaines.

### 3. Le jeton
```sh
export LINKEDIN_CLIENT_ID=xxx
export LINKEDIN_CLIENT_SECRET=yyy
python3 scripts/auth_linkedin.py
```
Le script ouvre LinkedIn, recupere le jeton et affiche `LINKEDIN_ACCESS_TOKEN` et
`LINKEDIN_PERSON_URN`. **Le jeton dure 60 jours et il n'existe pas de
rafraichissement automatique sans partenariat Marketing.** C'est pour ca que
`check_token.py` te previent 10 jours avant.

### 4. Le bot Telegram

1. Dans Telegram, parler a `@BotFather` -> `/newbot` -> un nom affiche, puis un
   identifiant qui finit par `bot`. Il rend le jeton : c'est `TELEGRAM_BOT_TOKEN`.
2. Envoyer un premier message a son propre bot, pour que la conversation existe :
   Telegram interdit a un bot d'ecrire le premier.
3. Recuperer le chat id et tester la boucle d'un coup :

```sh
python3 scripts/get_chat_id.py
```

Le script demande le jeton sans l'afficher, identifie le bot, liste les chat id
disponibles et envoie un message de confirmation dans Telegram.

Ne PAS passer par `https://api.telegram.org/bot<JETON>/getUpdates` dans un
navigateur, meme si la plupart des tutoriels le font : ca inscrit un jeton secret
dans l'historique de navigation et dans les logs. Le script fait la meme chose sans
laisser de trace, ni dans le navigateur, ni dans l'historique du shell.

### 5. La cle Claude
https://console.anthropic.com/ → API keys.

### 6. Les secrets GitHub
Settings → Secrets and variables → Actions → New repository secret :

| Secret | Valeur |
|---|---|
| `GOOGLE_API_KEY` | ta cle Gemini (le demarrage gratuit) |
| `LINKEDIN_ACCESS_TOKEN` | le jeton de l'etape 3 |
| `LINKEDIN_PERSON_URN` | `urn:li:person:xxxx` |
| `TELEGRAM_BOT_TOKEN` | le jeton du bot |
| `TELEGRAM_CHAT_ID` | ton chat id |

Plus tard, pour la bascule : secret `ANTHROPIC_API_KEY` et variable
`LLM_PROVIDER` = `claude`.

Variables optionnelles (onglet Variables) : `LLM_PROVIDER`, `GOOGLE_MODEL`,
`ANTHROPIC_MODEL`, `LINKEDIN_VERSION`, `POSTS_PER_RUN`.

### 7. Le socle editorial — rien ne bloque le demarrage
L'agent tourne des maintenant sans que tu aies rien a ecrire : la veille RSS lui
donne la matiere, et les piliers `pedagogie`, `coulisses` et `position` n'ont besoin
d'aucune donnee de ta part.

Deux fichiers montent en puissance avec le temps, sans effort de mise en route :

- `brand/corpus.md` **se remplit tout seul**. Chaque publication que tu valides a la
  main dans Telegram y est ajoutee et sert d'exemple aux suivantes. Plafonne a 12
  exemples : un modele qui s'imite trop longtemps derive, donc glisser de temps en
  temps un texte ecrit de ta main reste ce qui ameliore le plus le resultat.
- `brand/preuves.md` **verrouille le pilier chiffre**. Tant qu'il ne contient aucune
  ligne de donnee, l'agent ne propose jamais de publication chiffree : il ne peut pas
  inventer un resultat, donc il n'essaie pas. Des que tu y mets une vraie mesure, le
  pilier s'ouvre de lui-meme. C'est le pilier qui convertit le mieux, mais il attend
  ton premier chiffre reel, pas l'inverse.

### 8. Premier essai a blanc
```sh
cd scripts
python3 veille.py                # remplit la banque d'angles, aucune cle requise
GOOGLE_API_KEY=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... python3 generate.py
pip install -r ../requirements.txt && python3 -m playwright install chromium
DRY_RUN=1 python3 publish.py     # fabrique le visuel sans rien publier
open ../out/*.png
```
Quand le rendu et le texte te conviennent, retire `DRY_RUN` et active les workflows.

---

## Au quotidien

**Alimenter la machine, quand tu veux.** La veille tourne seule. Mais des que tu
envoies au bot une phrase sur ce que tu as fait — « automatise la relance devis chez
un cabinet, 3 h de dev, 5 h gagnees par semaine » — elle devient un angle et passe
devant les angles de veille. C'est la seule matiere que personne d'autre ne peut
ecrire a ta place, et c'est celle qui fait signer.

**Valider.** Les brouillons arrivent avec trois boutons : Publier, Rejeter, Reecrire.

**Suivre.** `/file` dans Telegram donne l'etat de la file.

**Chiffrer, une minute par mois.** `/stats` liste les publications parties dont on
n'a pas encore les chiffres. Tu reponds une ligne par publication :

```
013a26ea 1240 18 3
```

soit l'identifiant, les vues, les reactions, les commentaires. Les commentaires sont
facultatifs, et une phrase du genre `013a26ea : 1 240 vues, 18 reactions` passe aussi.

Pourquoi a la main : LinkedIn ne donne les statistiques d'un profil personnel qu'a une
application dediee au produit *Community Management API*, qui doit etre le seul produit
de l'application — il faudrait donc une deuxieme application LinkedIn et une deuxieme
autorisation. Une minute de saisie par mois evite ce detour tant que le compte est
jeune. Le jour ou il y aura une vingtaine de publications, la bascule vaudra le coup.

---

## La revue mensuelle

Le 1er de chaque mois, `revue.py` relit deux choses : tes decisions (ce que tu valides,
ce que tu fais reecrire, ce que tu refuses, par pilier, par gabarit, par source) et les
chiffres saisis. Il en tire une lecture, des regles de redaction a ajouter, une
experience a tenter — et **trois angles deposes dans la banque d'idees**, qui passent
devant la veille a la redaction suivante. La boucle se referme : ce qui a porte
commande ce qui s'ecrit ensuite.

Le rapport est ecrit dans `content/revues/AAAA-MM.md` et versionne. Le digest arrive
dans Telegram.

Garde-fou : en dessous de six publications mesurees, l'agent parle d'indice et non de
tendance, et il l'ecrit noir sur blanc. Un taux sur trois publications n'enseigne rien.

---

## Passer en autonomie complete

Critere de passage : 10 publications consecutives validees sans que tu retouches le
texte. Tant que tu reecris, le corpus n'est pas assez bon, et c'est le corpus qu'il
faut enrichir, pas l'agent qu'il faut lacher.

---

## Structure

```
brand/        le socle editorial, lu a chaque generation
content/      la file de contenus et les sources de veille, versionnees dans git
templates/    les 3 gabarits visuels, a la DA du site
scripts/      l'agent
  lib/        clients Claude, LinkedIn, Telegram, rendu PNG
.github/      les 6 workflows cron
```

## Points de vigilance

- **Horaires.** Les crons GitHub sont en UTC. Les horaires configures correspondent
  a l'heure d'ete francaise ; en hiver tout se decale d'une heure. A ajuster fin
  octobre si ca te gene.
- **En-tete de version LinkedIn.** `LINKEDIN_VERSION` vaut `202608`. LinkedIn retire
  les versions anciennes : si une publication echoue en 426, monte cette valeur.
- **Nom des modeles.** Laisse `GOOGLE_MODEL` et `ANTHROPIC_MODEL` vides : l'agent
  interroge le catalogue du fournisseur et prend le modele le plus recent
  utilisable. `generate.py` affiche en premiere ligne lequel il a retenu.
- **Quotas Gemini gratuits.** Le palier gratuit limite les requetes par minute et
  par jour. L'agent fait six appels par semaine, on en est tres loin. Si un jour
  ca coince en 429, c'est le signal pour basculer sur Claude.
- **Ne jamais publier via automatisation du navigateur.** L'API officielle est le
  seul canal sur.
