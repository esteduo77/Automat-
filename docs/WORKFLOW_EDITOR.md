# Éditeur de workflows — Automation Hub

## Décisions produit
- Éditeur : canvas libre, avec blocs déplaçables et connexions visibles.
- Organisation : bibliothèque de blocs classée par catégories.
- Exécution : politique de validation configurable au niveau de chaque bloc.
- Le canvas décrit un workflow ; le serveur reste seul responsable de sa validation et de son exécution.

## Expérience utilisateur
L'écran de création comporte quatre zones :
1. Bibliothèque latérale : recherche et catégories de blocs.
2. Canvas central : espace quadrillé, déplacement, zoom, sélection et connexions.
3. Inspecteur latéral : paramètres du bloc, entrées/sorties et politique de validation.
4. Barre supérieure : nom, état brouillon/actif, Tester, Enregistrer et Activer.

Sur petit écran, bibliothèque et inspecteur deviennent des panneaux repliables ; le canvas conserve la priorité.

## Catégories de blocs

| Catégorie | Rôle | Exemples |
|---|---|---|
| Déclencheurs | Démarrer un workflow | Manuel, horaire, nouvel e-mail, nouveau fichier |
| IA | Comprendre ou préparer du contenu | Résumer, classifier, extraire des champs, rédiger un brouillon |
| Google | Interagir avec Google Workspace | Rechercher un e-mail, lire un fichier, créer un document |
| Microsoft | Interagir avec Microsoft 365 | Rechercher un message, lire un fichier, créer un événement |
| Fichiers & données | Transformer ou organiser des données | Filtrer, convertir, mapper des champs |
| Conditions | Choisir une branche | Si/alors/sinon, comparaison, correspondance |
| Validation | Demander une décision humaine | Approbation, rejet, commentaire |
| Sorties | Terminer ou transmettre | Notification, résultat, journal |

La bibliothèque n'affiche que les blocs réellement disponibles. Les intégrations non configurées restent marquées « bientôt disponibles » et ne peuvent pas être exécutées.

## Modèle du workflow
Un workflow est un graphe orienté composé de nœuds et de connexions.

- Workflow : id, name, description, status, version, created_at, updated_at.
- Node : id stable, type, category, position {x, y}, config, approval_policy.
- Edge : id, source_node_id, source_port, target_node_id, target_port.
- WorkflowRun : id, workflow_id, workflow_version, status, started_at, finished_at.
- NodeRun : id, run_id, node_id, status, input_summary, output_summary, error, timestamps.
- Approval : id, node_run_id, requested_by, decision, comment, decided_at.
- AuditEvent : acteur, action, cible, horodatage et résultat.

Les identifiants de nœuds restent stables entre les sauvegardes afin de préserver les connexions. Une exécution référence une version immuable du workflow : modifier un brouillon ne change jamais une exécution déjà lancée.

## Contrat d'un bloc
Chaque type de bloc déclare :
- un identifiant de type versionné ;
- sa catégorie et son libellé ;
- un schéma de configuration validé côté serveur ;
- ses ports d'entrée et de sortie typés ;
- ses capacités et autorisations requises ;
- son niveau de risque ;
- sa politique de validation par défaut ;
- son exécuteur serveur, s'il est activé.

Le frontend utilise un registre de métadonnées pour afficher la bibliothèque et les formulaires. Ce registre ne constitue pas une autorisation d'exécution : le backend revalide chaque nœud et chaque connexion.

## Politique de validation configurable
Chaque bloc possède une politique explicite :
- always : approbation humaine obligatoire avant l'action ;
- on_risk : approbation si l'action est classée sensible ;
- never : aucune étape d'approbation supplémentaire, uniquement pour les opérations sûres et réversibles autorisées.

La politique effective ne peut pas être moins stricte que le niveau minimal imposé par le serveur. Un bloc d'envoi, de partage externe, de suppression ou de modification importante exige toujours une confirmation explicite, même si le workflow est activé. Une approbation est liée à une exécution, un nœud, une version et un résumé précis de l'action ; tout changement de paramètres invalide cette approbation.

L'activation d'un workflow ne vaut jamais approbation de ses futures actions sensibles.

## Cycle d'exécution
1. L'utilisateur lance un test ou un workflow activé.
2. L'API charge une version validée et vérifie les permissions et intégrations.
3. Le moteur construit un plan à partir du graphe ; il rejette les connexions invalides, les cycles non pris en charge et les types incompatibles.
4. Les nœuds sont exécutés dans l'ordre des dépendances, avec limites de durée, de tentatives et de ressources.
5. Lorsqu'une approbation est nécessaire, l'exécution passe à waiting_approval et s'arrête avant l'action.
6. Après approbation explicite, le serveur revalide les paramètres et les autorisations, puis reprend l'exécution.
7. Les résultats, erreurs et décisions sont consignés dans l'historique.

Le premier moteur sera séquentiel et déterministe. Les branches conditionnelles seront prises en charge ; les boucles, exécutions parallèles et sous-workflows sont reportés à une version ultérieure.

## API proposée
- POST /api/workflows — créer un brouillon.
- GET /api/workflows et GET /api/workflows/{id} — lister et lire.
- PUT /api/workflows/{id} — sauvegarder un brouillon avec validation du graphe.
- POST /api/workflows/{id}/validate — obtenir les erreurs et avertissements.
- POST /api/workflows/{id}/test — lancer un test contrôlé.
- POST /api/workflows/{id}/activate — activer une version validée.
- POST /api/workflows/{id}/runs — lancer une exécution manuelle.
- GET /api/runs/{id} — consulter l'état et les étapes.
- POST /api/approvals/{id}/decision — approuver ou refuser une action en attente.

Ces routes décrivent la cible ; elles ne sont pas toutes implémentées à ce stade.

## Architecture technique cible

### Frontend
- React + TypeScript.
- Bibliothèque de canvas recommandée : React Flow (@xyflow/react) pour les nœuds personnalisés, les ports, le zoom et le déplacement.
- Modèle sérialisé indépendant de la bibliothèque d'affichage.
- Formulaires de configuration générés depuis les schémas de blocs.
- Validation ergonomique immédiate côté client, répétée côté serveur.

### Backend
- FastAPI expose les routes et valide les schémas.
- Un service Workflow gère les versions, la validation et l'activation.
- Un moteur d'exécution orchestre les nœuds et les états d'exécution.
- Des adaptateurs isolent OpenAI, Google et Microsoft.
- Une couche de persistance stocke workflows, versions, exécutions, approbations et événements d'audit.
- Les secrets et jetons OAuth restent côté serveur ; le navigateur ne reçoit jamais les clés fournisseurs.

## Sécurité et fiabilité
- Liste blanche de types de blocs exécutables ; aucune exécution de code arbitraire fourni par l'utilisateur.
- Validation stricte des configurations, ports, tailles et connexions.
- Autorisations minimales par intégration et par action.
- Secrets masqués dans les logs et les réponses API.
- Idempotence des actions lorsque le fournisseur le permet.
- Limites de durée, taille, débit et nombre de tentatives.
- Journal d'audit append-only pour les décisions et actions importantes.
- Mode test sans effet externe par défaut.
- Pas d'envoi d'e-mail, suppression ou partage externe tant que l'intégration et le parcours d'approbation n'ont pas été implémentés et testés.

## Exemple de workflow
Déclencheur manuel → Analyser le contenu avec l'IA → Condition : catégorie = facture ?

- Branche oui → Préparer le classement → Approbation → Déplacer le fichier.
- Branche non → Créer un résumé → Afficher le résultat.

Le déplacement n'a lieu qu'après validation si la politique du bloc l'exige.

## Plan de réalisation
1. Fondations de l'éditeur : installer React Flow, créer le canvas, les nœuds visuels, la bibliothèque par catégories et l'inspecteur.
2. Modèle et sauvegarde : schémas TypeScript/Pydantic, validation de graphe, brouillons et versions.
3. Exécution sûre : moteur séquentiel, runs, journal, mode test et approbations par nœud.
4. Premiers blocs actifs : déclencheur manuel, condition, transformation de données et blocs IA sans effet externe.
5. Intégrations : Google et Microsoft avec OAuth, permissions minimales et approbation obligatoire des actions sensibles.

## État actuel
Un premier éditeur frontend est maintenant présent : canvas React Flow, blocs de démonstration déplaçables et connectables, bibliothèque filtrable par catégories, inspecteur de bloc, politique de validation configurable, validation locale de la structure et sauvegarde/restauration du brouillon dans le navigateur. Les blocs Google et Microsoft sont affichés comme indisponibles tant que les intégrations ne sont pas configurées. Le moteur backend, les API workflows, la persistance serveur, les exécutions réelles et les approbations ne sont pas encore implémentés.
