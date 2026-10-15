# Le pont de publication

Tant que LinkedIn n'a pas accorde le produit Community Management API a
l'application de la page, `LINKEDIN_ORG_ACCESS_TOKEN` n'existe pas et
`publish.py` ne peut pas publier par l'API.

La regle ne change pas : aucun repli sur le profil personnel. La page est le
seul auteur.

Au creneau de publication, sans jeton de page, l'agent fait donc tout le
chemin sauf le dernier metre :

1. il fabrique le visuel du brouillon le plus ancien en file ;
2. il l'envoie dans Telegram en piece jointe PNG, sans recompression, parce
   que c'est ce fichier-la qui remonte ensuite sur LinkedIn ;
3. il envoie le texte seul, pour qu'il se copie d'un geste ;
4. il joint deux boutons : *Ouvrir la page*, qui mene au composeur de la
   page, et *Publie*, qui fait avancer la file.

Le brouillon reste `approved` jusqu'au clic sur *Publie*. Si Younes ne
publie pas ce jour-la, rien n'est perdu : le pont se repropose le lendemain.
Un drapeau `pont_envoye_le` dans l'etat de la file empeche deux propositions
le meme jour.

Le jour ou le jeton arrive, le bloc n'est plus atteint. Il n'y a rien a
defaire.
