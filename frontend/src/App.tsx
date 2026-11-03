import { useCallback, useEffect, useMemo, useState } from "react";
import {
  addEdge,
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Connection,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";

type Policy = "always" | "on_risk" | "never";
type BlockData = {
  label: string;
  description: string;
  category: string;
  policy: Policy;
  config?: Record<string, unknown>;
};

type HubNode = Node<BlockData, "hub">;

const initialNodes: HubNode[] = [
  {
    id: "manual-start",
    type: "hub",
    position: { x: 100, y: 170 },
    data: {
      label: "Déclencheur manuel",
      description: "Démarre le workflow à la demande.",
      category: "Déclencheurs",
      policy: "never",
    },
  },
  {
    id: "ai-summary",
    type: "hub",
    position: { x: 440, y: 170 },
    data: {
      label: "Analyser avec l'IA",
      description: "Prépare une analyse structurée du contenu.",
      category: "IA",
      policy: "on_risk",
    },
  },
  {
    id: "approval",
    type: "hub",
    position: { x: 780, y: 170 },
    data: {
      label: "Validation humaine",
      description: "Attend une décision avant de continuer.",
      category: "Validation",
      policy: "always",
    },
  },
];

const initialEdges: Edge[] = [
  { id: "start-ai", source: "manual-start", target: "ai-summary", animated: true },
  { id: "ai-approval", source: "ai-summary", target: "approval", animated: true },
];

const catalog = [
  { category: "Déclencheurs", icon: "◷", blocks: [{ label: "Déclencheur manuel", description: "Lancer à la demande." }, { label: "Déclencheur planifié", description: "Démarrer selon un horaire." }, { label: "Déclencheur webhook", description: "Démarrer à la réception d’un événement signé." }] },
  { category: "IA", icon: "✦", blocks: [{ label: "Analyser avec l'IA", description: "Analyser un texte ou un contenu." }, { label: "Résumer un contenu", description: "Créer un résumé structuré." }, { label: "Classer un contenu", description: "Attribuer une catégorie." }] },
  { category: "Conditions", icon: "⑂", blocks: [{ label: "Condition si / sinon", description: "Diriger le workflow selon un test." }] },
  { category: "Validation", icon: "✓", blocks: [{ label: "Validation humaine", description: "Demander une approbation explicite." }] },
  { category: "Fichiers & données", icon: "▤", blocks: [{ label: "Transformer des données", description: "Nettoyer ou convertir des champs." }] },
  { category: "Google", icon: "G", blocks: [{ label: "Rechercher un e-mail", description: "Rechercher des messages Gmail." }, { label: "Rechercher un fichier", description: "Rechercher des fichiers Google Drive." }, { label: "Envoyer un e-mail", description: "Envoyer après approbation humaine." }, { label: "Créer un fichier", description: "Créer un fichier Drive après approbation." }, { label: "Modifier un fichier", description: "Mettre à jour un fichier Drive après approbation." }] },
  { category: "Microsoft", icon: "▦", blocks: [{ label: "Rechercher un message", description: "Rechercher des messages Outlook." }, { label: "Rechercher un fichier", description: "Rechercher des fichiers OneDrive." }, { label: "Envoyer un e-mail", description: "Envoyer après approbation humaine." }, { label: "Créer un fichier", description: "Créer un fichier OneDrive après approbation." }, { label: "Modifier un fichier", description: "Mettre à jour un fichier OneDrive après approbation." }] },
  { category: "Sorties", icon: "↗", blocks: [{ label: "Afficher un résultat", description: "Terminer avec un résultat visible." }] },
];

function WorkflowNode({ data, selected }: NodeProps<HubNode>) {
  return (
    <div className={`workflow-node ${selected ? "selected" : ""}`}>
      <Handle type="target" position={Position.Left} />
      <div className="node-topline">
        <span className="node-category">{data.category}</span>
        <span className="node-dot" />
      </div>
      <strong>{data.label}</strong>
      <p>{data.description}</p>
      <div className="node-policy">Validation : {data.policy === "always" ? "toujours" : data.policy === "on_risk" ? "si sensible" : "non requise"}</div>
      {data.category === "Conditions" ? <><Handle id="true" type="source" position={Position.Right} style={{ top: "38%" }} /><Handle id="false" type="source" position={Position.Right} style={{ top: "72%" }} /></> : <Handle type="source" position={Position.Right} />}
    </div>
  );
}

const nodeTypes = { hub: WorkflowNode };

type SavedDraft = { name?: string; nodes?: HubNode[]; edges?: Edge[] };
function readDraft(): SavedDraft | null {
  try {
    const raw = window.localStorage.getItem("automation-hub-workflow-draft");
    if (!raw) return null;
    const parsed = JSON.parse(raw) as SavedDraft;
    return Array.isArray(parsed.nodes) && Array.isArray(parsed.edges) ? parsed : null;
  } catch {
    return null;
  }
}

function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const headers = new Headers(init.headers);
  const token = window.localStorage.getItem("automation-hub-token");
  if (token) headers.set("Authorization", "Bearer " + token);
  const apiBase = (import.meta.env.VITE_API_URL ?? "").replace(/\\/$/, "");
  const url = typeof input === "string" && input.startsWith("/api/") ? apiBase + input : input;
  return fetch(url, { ...init, headers });
}

export default function App() {
  const savedDraft = useMemo(() => readDraft(), []);
  const [nodes, setNodes, onNodesChange] = useNodesState<HubNode>(savedDraft?.nodes ?? initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(savedDraft?.edges ?? initialEdges);
  const [selectedId, setSelectedId] = useState<string | null>(savedDraft?.nodes?.[1]?.id ?? "ai-summary");
  const [search, setSearch] = useState("");
  const [notice, setNotice] = useState("Reliez les blocs pour composer votre automatisation.");
  const [workflowName, setWorkflowName] = useState(savedDraft?.name ?? "Mon premier workflow");
  const [activeCategory, setActiveCategory] = useState("Tous");
  const [workflowId, setWorkflowId] = useState<string | null>(() => window.localStorage.getItem("automation-hub-workflow-id"));
  const [apiStatus, setApiStatus] = useState("API non vérifiée");
  const [savedWorkflows, setSavedWorkflows] = useState<Array<{id:string;name:string}>>([]);
  const [runStatus, setRunStatus] = useState<string | null>(null);
  const [pendingApprovalId, setPendingApprovalId] = useState<string | null>(null);
  const [pendingApprovalSummary, setPendingApprovalSummary] = useState("");
  const [history, setHistory] = useState<Array<{id:string;status:string;started_at:string}>>([]);
  const [showHistory, setShowHistory] = useState(false);
  const [integrations, setIntegrations] = useState<Record<string, {configured:boolean;connected:boolean;account:string|null}>>({});
  const [runInput, setRunInput] = useState("{\"score\":10,\"text\":\"Exemple de contenu\"}");
  const [scheduleId, setScheduleId] = useState<string | null>(null);
  const [authToken, setAuthToken] = useState<string | null>(() => window.localStorage.getItem("automation-hub-token"));
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authError, setAuthError] = useState("");
  const [webhookInfo, setWebhookInfo] = useState<{path:string;secret:string}|null>(null);

  const selectedNode = nodes.find((node) => node.id === selectedId) ?? null;

  useEffect(() => {
    apiFetch("/api/health").then((response) => { if (!response.ok) throw new Error(); setApiStatus("API connectée"); }).catch(() => setApiStatus("API indisponible"));
    if (!authToken) return;
    apiFetch("/api/integrations").then((response) => { if (!response.ok) throw new Error(); return response.json(); }).then(setIntegrations).catch(() => setIntegrations({}));
    apiFetch("/api/workflows").then((response) => { if (!response.ok) throw new Error(); return response.json(); }).then(setSavedWorkflows).catch(() => setSavedWorkflows([]));
  }, [authToken]);
  const categories = useMemo(() => ["Tous", ...catalog.map((item) => item.category)], []);
  const visibleCatalog = catalog.filter((group) => {
    const categoryMatches = activeCategory === "Tous" || activeCategory === group.category;
    const searchMatches = group.category.toLowerCase().includes(search.toLowerCase()) ||
      group.blocks.some((block) => block.label.toLowerCase().includes(search.toLowerCase()));
    return categoryMatches && searchMatches;
  });

  const onConnect = useCallback((connection: Connection) => {
    setEdges((current) => addEdge({ ...connection, animated: true }, current));
    setNotice("Connexion ajoutée au canvas.");
  }, [setEdges]);

  const addBlock = (category: string, label: string, description: string) => {
    const id = `block-${Date.now()}`;
    const node: HubNode = {
      id,
      type: "hub",
      position: { x: 180 + (nodes.length % 3) * 80, y: 100 + nodes.length * 34 },
      data: { category, label, description, policy: category === "Validation" ? "always" : category === "IA" ? "on_risk" : "never", config: category === "Conditions" ? { field: "score", operator: "equals", value: 10 } : (category === "Google" || category === "Microsoft") ? { query: "", limit: 10 } : (category === "Déclencheurs" && label.includes("planifié")) ? { interval_seconds: 300 } : {} },
    };
    setNodes((current) => [...current, node]);
    setSelectedId(id);
    setNotice(`Bloc « ${label} » ajouté. Déplacez-le et reliez-le aux autres blocs.`);
  };

  const updateSelected = (patch: Partial<BlockData>) => {
    if (!selectedId) return;
    setNodes((current) => current.map((node) =>
      node.id === selectedId ? { ...node, data: { ...node.data, ...patch } } : node
    ));
  };

  const validateWorkflow = () => {
    const errors: string[] = [];
    if (nodes.length === 0) errors.push("Ajoutez au moins un bloc.");
    if (nodes.filter((node) => node.data.category === "Déclencheurs").length === 0) errors.push("Ajoutez un déclencheur.");
    const connected = new Set(edges.flatMap((edge) => [edge.source, edge.target]));
    if (nodes.length > 1 && connected.size < nodes.length) errors.push("Certains blocs ne sont pas reliés.");
    if (errors.length) setNotice(`À corriger : ${errors.join(" ")}`);
    else setNotice("Structure valide pour cette prévisualisation. Aucune action externe n'a été exécutée.");
  };

  const saveDraft = async () => {
    const draft = { name: workflowName, nodes, edges, savedAt: new Date().toISOString() };
    window.localStorage.setItem("automation-hub-workflow-draft", JSON.stringify(draft));
    try {
      const url = workflowId ? "/api/workflows/" + workflowId : "/api/workflows";
      const response = await apiFetch(url, { method: workflowId ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: workflowName, nodes, edges }) });
      const saved = await response.json();
      if (!response.ok) throw new Error(String(saved.detail ?? "Échec de sauvegarde API"));
      setWorkflowId(saved.id); window.localStorage.setItem("automation-hub-workflow-id", saved.id);
      setSavedWorkflows((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      setNotice("Workflow enregistré dans la base de données."); setApiStatus("API connectée");
    } catch (error) { setNotice("Brouillon local enregistré ; API indisponible : " + (error instanceof Error ? error.message : "erreur")); }
  };

  const loadWorkflow = async (id: string) => {
    if (!id) return;
    try {
      const response = await apiFetch("/api/workflows/" + id);
      const saved = await response.json();
      if (!response.ok) throw new Error(String(saved.detail ?? "Chargement impossible"));
      setWorkflowId(saved.id); setWorkflowName(saved.name);
      setNodes(saved.graph.nodes); setEdges(saved.graph.edges);
      window.localStorage.setItem("automation-hub-workflow-id", saved.id);
      window.localStorage.setItem("automation-hub-workflow-draft", JSON.stringify({ name: saved.name, nodes: saved.graph.nodes, edges: saved.graph.edges }));
      setSelectedId(saved.graph.nodes[0]?.id ?? null); setNotice("Workflow chargé depuis la base de données.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Erreur de chargement"); }
  };

  const loadHistory = async () => {
    if (!workflowId) return;
    try { const response = await apiFetch("/api/workflows/" + workflowId + "/runs"); if (response.ok) setHistory(await response.json()); } catch { setNotice("Impossible de charger l’historique."); }
  };

  const pollRun = async (runId: string) => {
    for (let attempt = 0; attempt < 60; attempt += 1) {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      try {
        const response = await apiFetch("/api/workflows/runs/" + runId);
        if (!response.ok) return;
        const result = await response.json();
        setRunStatus(result.status);
        const approval = result.approvals?.find((item: {status:string;id:string;summary?:string}) => item.status === "pending");
        if (approval) {
          setPendingApprovalId(approval.id);
          setPendingApprovalSummary(approval.summary ?? "Action externe en attente de validation.");
          setNotice("Une approbation humaine est nécessaire avant de poursuivre.");
          loadHistory();
          return;
        }
        if (["completed", "failed", "rejected"].includes(result.status)) {
          setNotice("Exécution terminée : " + result.status);
          loadHistory();
          return;
        }
      } catch { return; }
    }
    setNotice("L’exécution continue en arrière-plan. Consultez l’historique pour son état.");
  };

  const runWorkflow = async () => {
    if (!workflowId) { setNotice("Enregistrez d’abord le workflow dans la base de données."); return; }
    let input: Record<string, unknown>;
    try { input = JSON.parse(runInput) as Record<string, unknown>; } catch { setNotice("Les entrées doivent être un JSON valide."); return; }
    try {
      const response = await apiFetch("/api/workflows/" + workflowId + "/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ input }) });
      const result = await response.json(); if (!response.ok) throw new Error(String(result.detail ?? "Exécution impossible"));
      setRunStatus(result.status); setPendingApprovalId(null); setNotice("Exécution placée en file : " + result.status); loadHistory(); void pollRun(result.id);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Erreur d’exécution"); }
  };

  const scheduleWorkflow = async () => {
    if (!workflowId) { setNotice("Enregistrez d’abord le workflow avant de le planifier."); return; }
    try {
      const response = await apiFetch("/api/automations/workflows/" + workflowId + "/schedule", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ interval_seconds: Number(nodes.find((node) => node.data.category === "Déclencheurs" && node.data.label.toLowerCase().includes("planifié"))?.data.config?.interval_seconds ?? 300) }) });
      const result = await response.json(); if (!response.ok) throw new Error(String(result.detail ?? "Planification impossible"));
      setScheduleId(result.id); setNotice("Déclencheur actif : exécution toutes les 5 minutes.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Erreur de planification"); }
  };

  const pauseSchedule = async () => {
    if (!scheduleId) return;
    try { const response = await apiFetch("/api/automations/" + scheduleId + "/pause", { method: "POST" }); if (!response.ok) throw new Error("Pause impossible."); setScheduleId(null); setNotice("Déclencheur mis en pause."); }
    catch (error) { setNotice(error instanceof Error ? error.message : "Erreur"); }
  };

  const decideApproval = async (decision: "approve" | "reject") => {
    if (!pendingApprovalId) return;
    const response = await apiFetch("/api/workflows/approvals/" + pendingApprovalId + "/decision", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ decision }) });
    const result = await response.json(); if (!response.ok) { setNotice(String(result.detail ?? "Décision refusée")); return; }
    setRunStatus(result.status); setPendingApprovalId(null); setPendingApprovalSummary(""); setNotice("Décision enregistrée : " + result.status); loadHistory(); if (decision === "approve") void pollRun(result.id);
  };

  const createWebhook = async () => {
    if (!workflowId) { setNotice("Enregistrez le workflow avant de créer son webhook."); return; }
    try {
      const response = await apiFetch("/api/webhooks/workflows/" + workflowId + "/endpoint", { method: "POST" });
      const result = await response.json();
      if (!response.ok) throw new Error(String(result.detail ?? "Création du webhook impossible."));
      setWebhookInfo({ path: result.path, secret: result.secret });
      setNotice("Webhook créé. Copiez son secret maintenant : il ne sera plus affiché.");
    } catch (error) { setNotice(error instanceof Error ? error.message : "Erreur webhook."); }
  };

  const startOAuth = async (provider: "google" | "microsoft") => {
    try {
      const response = await apiFetch("/api/integrations/" + provider + "/connect");
      const result = await response.json();
      if (!response.ok) throw new Error(String(result.detail ?? "Connexion fournisseur impossible."));
      window.location.assign(result.authorization_url);
    } catch (error) { setNotice(error instanceof Error ? error.message : "Erreur OAuth."); }
  };

  const authenticate = async () => {
    setAuthError("");
    try {
      const response = await apiFetch("/api/auth/" + authMode, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: authEmail, password: authPassword }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(String(result.detail ?? "Authentification impossible."));
      window.localStorage.setItem("automation-hub-token", result.access_token);
      setAuthToken(result.access_token); setAuthPassword("");
    } catch (error) { setAuthError(error instanceof Error ? error.message : "Erreur de connexion."); }
  };

  if (!authToken) return (
    <main className="workspace">
      <section className="inspector-panel" style={{ maxWidth: 480, margin: "10vh auto", padding: 32 }}>
        <span className="eyebrow">AUTOMATION HUB</span><h1>{authMode === "login" ? "Connexion" : "Créer un compte"}</h1>
        <p>Connectez-vous pour accéder à vos workflows et à vos comptes cloud privés.</p>
        <label className="field-label">Adresse e-mail<input type="email" autoComplete="email" value={authEmail} onChange={(event) => setAuthEmail(event.target.value)} /></label>
        <label className="field-label">Mot de passe<input type="password" minLength={authMode === "register" ? 12 : undefined} autoComplete={authMode === "login" ? "current-password" : "new-password"} value={authPassword} onChange={(event) => setAuthPassword(event.target.value)} /></label>
        {authMode === "register" && <small>12 caractères minimum.</small>}
        {authError && <p role="alert">{authError}</p>}
        <button className="button button-primary" onClick={authenticate}>{authMode === "login" ? "Se connecter" : "Créer mon compte"}</button>
        <button className="button button-quiet" onClick={() => setAuthMode(authMode === "login" ? "register" : "login")}>{authMode === "login" ? "Créer un compte" : "J’ai déjà un compte"}</button>
      </section>
    </main>
  );

  return (
    <main className="workspace">
      <header className="editor-header">
        <a className="back-link brand-link" href="/">AH <span>Automation Hub</span></a>
        <div className="workflow-title">
          <span className="eyebrow">ÉDITEUR DE WORKFLOWS</span>
          <input aria-label="Nom du workflow" value={workflowName} onChange={(event) => setWorkflowName(event.target.value)} />
        </div>
        <span className="draft-status"><i /> Brouillon</span>
        <span className="draft-status">{apiStatus}</span>
        <button className="button button-quiet" onClick={() => { window.localStorage.removeItem("automation-hub-token"); window.localStorage.removeItem("automation-hub-workflow-id"); window.localStorage.removeItem("automation-hub-workflow-draft"); setAuthToken(null); setWorkflowId(null); setNodes(initialNodes); setEdges(initialEdges); }}>Déconnexion</button>
        <button className="button button-quiet" onClick={validateWorkflow}>Valider</button>
        <button className="button button-quiet" onClick={runWorkflow}>Exécuter</button>
        {scheduleId ? <button className="button button-quiet" onClick={pauseSchedule}>Pause planification</button> : <button className="button button-quiet" onClick={scheduleWorkflow}>Planifier · 5 min</button>}
        <button className="button button-quiet" onClick={createWebhook}>Créer webhook</button>
        <button className="button button-primary" onClick={saveDraft}>Enregistrer</button>
      </header>

      <div className="editor-layout">
        <aside className="library-panel">
          <div className="panel-heading"><div><span className="eyebrow">CONSTRUIRE</span><h2>Blocs</h2></div><span className="count">{catalog.reduce((sum, group) => sum + group.blocks.length, 0)}</span></div>
          <input className="search-input" placeholder="Rechercher un bloc…" value={search} onChange={(event) => setSearch(event.target.value)} />
          <div className="category-filter">
            {categories.map((category) => <button key={category} className={activeCategory === category ? "category-chip active" : "category-chip"} onClick={() => setActiveCategory(category)}>{category}</button>)}
          </div>
          <div className="block-groups">
            {visibleCatalog.map((group) => (
              <section className="block-group" key={group.category}>
                <h3><span>{group.icon}</span>{group.category}</h3>
                {group.blocks.map((block) => {
                  const unavailable = false;
                  return <button key={block.label} className="library-block" disabled={unavailable} onClick={() => addBlock(group.category, block.label, block.description)}>
                    <span className="add-symbol">+</span><span><strong>{block.label}</strong><small>{unavailable ? "Bientôt disponible" : block.description}</small></span>
                  </button>;
                })}
              </section>
            ))}
            {visibleCatalog.length === 0 && <p className="empty-state">Aucun bloc ne correspond à cette recherche.</p>}
          </div>
          <section className="block-group integration-links">
            <h3>Connexions de comptes</h3>
            <button className="connect-link" onClick={() => startOAuth("google")}>{integrations.google?.connected ? "Google connecté · " + integrations.google.account : "Connecter Google"}</button>
            <button className="connect-link" onClick={() => startOAuth("microsoft")}>{integrations.microsoft?.connected ? "Microsoft connecté · " + integrations.microsoft.account : "Connecter Microsoft"}</button>
            <small>Recherche et actions d’écriture approuvées. Configurez les permissions OAuth côté serveur.</small>
          </section>
        </aside>

        <section className="canvas-panel" aria-label="Canvas du workflow">
          <div className="canvas-toolbar"><div><span className="eyebrow">ESPACE DE TRAVAIL</span><strong>Canvas</strong></div><span className="canvas-hint">Glissez les blocs · Reliez les ports</span></div>
          <div className="flow-wrap">
            <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={(_, node) => setSelectedId(node.id)} onPaneClick={() => setSelectedId(null)} fitView minZoom={0.25} maxZoom={1.5} defaultEdgeOptions={{ type: "smoothstep" }}>
              <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="#34445a" />
              <Controls />
              <MiniMap pannable zoomable nodeColor="#82d9b8" maskColor="rgba(7, 14, 25, 0.68)" />
            </ReactFlow>
          </div>
          {webhookInfo && <div className="history-panel"><strong>Endpoint webhook</strong><p>{webhookInfo.path}</p><p>Secret à conserver : {webhookInfo.secret}</p></div>}<div className="canvas-footer"><span>{nodes.length} blocs</span><span>{edges.length} connexions</span><button className="history-toggle" onClick={() => { setShowHistory(!showHistory); loadHistory(); }}>Historique</button>{pendingApprovalId && <><span className="notice">{pendingApprovalSummary}</span><button className="history-toggle" onClick={() => decideApproval("approve")}>Approuver</button><button className="history-toggle" onClick={() => decideApproval("reject")}>Refuser</button></>}<span className="notice">{notice}</span></div><div className="run-input"><label>Entrées de test (JSON)<input value={runInput} onChange={(event) => setRunInput(event.target.value)} /></label>{runStatus && <span>Dernière exécution : {runStatus}</span>}</div>{showHistory && <div className="history-panel"><strong>Historique des exécutions</strong>{history.length ? history.slice(0,6).map((item) => <div key={item.id}>{item.id.slice(0,8)} · {item.status} · {new Date(item.started_at).toLocaleString()}</div>) : <p>Aucune exécution enregistrée.</p>}</div>}
        </section>

        <aside className="inspector-panel">
          <div className="panel-heading"><div><span className="eyebrow">PARAMÈTRES</span><h2>Inspecteur</h2></div><span className="inspector-icon">☷</span></div>
          {selectedNode ? <>
            <div className="selected-block"><span className="eyebrow">{selectedNode.data.category}</span><strong>{selectedNode.data.label}</strong><p>{selectedNode.data.description}</p></div>
            <label className="field-label">Nom du bloc<input value={selectedNode.data.label} onChange={(event) => updateSelected({ label: event.target.value })} /></label>
            <label className="field-label">Description<textarea rows={3} value={selectedNode.data.description} onChange={(event) => updateSelected({ description: event.target.value })} /></label>
            {selectedNode.data.category === "Conditions" && <div className="policy-section"><span className="eyebrow">BRANCHEMENT IF / ELSE</span><label className="field-label">Champ d'entrée<input value={String(selectedNode.data.config?.field ?? "score")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, field: event.target.value } })} /></label><label className="field-label">Opérateur<select value={String(selectedNode.data.config?.operator ?? "equals")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, operator: event.target.value } })}><option value="equals">Égal à</option><option value="not_equals">Différent de</option><option value="contains">Contient</option><option value="is_true">Est vrai</option><option value="is_false">Est faux</option></select></label><label className="field-label">Valeur<input value={String(selectedNode.data.config?.value ?? "")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, value: event.target.value } })} /></label><p>Sortie verte : vrai. Sortie orange : faux.</p></div>}
            {selectedNode.data.category === "Déclencheurs" && selectedNode.data.label.toLowerCase().includes("planifié") && <div className="policy-section"><span className="eyebrow">FRÉQUENCE DU DÉCLENCHEUR</span><label className="field-label">Intervalle en secondes (minimum 60)<input type="number" min="60" max="31536000" value={Number(selectedNode.data.config?.interval_seconds ?? 300)} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, interval_seconds: Math.max(60, Number(event.target.value)) } })} /></label><p>La planification est persistée côté serveur et traitée par le worker.</p></div>}
            {(selectedNode.data.category === "Google" || selectedNode.data.category === "Microsoft") && <div className="policy-section"><span className="eyebrow">PARAMÈTRES DU CONNECTEUR</span><label className="field-label">Requête<input value={String(selectedNode.data.config?.query ?? "")} placeholder="Ex. facture" onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, query: event.target.value } })} /></label><label className="field-label">Nombre de résultats<input type="number" min="1" max="50" value={Number(selectedNode.data.config?.limit ?? 10)} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, limit: Number(event.target.value) } })} /></label>{selectedNode.data.label.toLowerCase().includes("envoyer") && <><label className="field-label">Destinataire<input type="email" value={String(selectedNode.data.config?.to ?? "")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, to: event.target.value } })} /></label><label className="field-label">Objet<input value={String(selectedNode.data.config?.subject ?? "")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, subject: event.target.value } })} /></label><label className="field-label">Message<textarea rows={4} value={String(selectedNode.data.config?.body ?? "")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, body: event.target.value } })} /></label></>}{selectedNode.data.label.toLowerCase().includes("fichier") && <><label className="field-label">Nom / chemin<input value={String(selectedNode.data.config?.name ?? selectedNode.data.config?.path ?? "")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, name: event.target.value, path: event.target.value } })} /></label><label className="field-label">Identifiant du fichier (pour modifier)<input value={String(selectedNode.data.config?.file_id ?? "")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, file_id: event.target.value } })} /></label><label className="field-label">Contenu<textarea rows={4} value={String(selectedNode.data.config?.content ?? "")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, content: event.target.value } })} /></label></>}<p>Les actions d’écriture attendent une approbation humaine côté serveur.</p></div>}
            {selectedNode.data.category === "IA" && <div className="policy-section"><span className="eyebrow">PARAMÈTRES IA</span><label className="field-label">Instruction<input value={String(selectedNode.data.config?.prompt ?? "")} placeholder="Résume le contenu en 3 points…" onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, prompt: event.target.value } })} /></label><label className="field-label">Texte (facultatif)<textarea rows={3} value={String(selectedNode.data.config?.text ?? "")} onChange={(event) => updateSelected({ config: { ...selectedNode.data.config, text: event.target.value } })} /></label></div>}
            <div className="policy-section"><span className="eyebrow">EXÉCUTION</span><h3>Validation humaine</h3><p>Choisissez quand ce bloc doit attendre une approbation.</p>
              <label className="field-label">Politique<select value={selectedNode.data.policy} onChange={(event) => updateSelected({ policy: event.target.value as Policy })}>
                <option value="always">Toujours demander</option>
                <option value="on_risk">Seulement si sensible</option>
                <option value="never">Pas de validation supplémentaire</option>
              </select></label>
              <div className="security-note">Les actions sensibles resteront soumises aux règles de sécurité du serveur, quelle que soit cette option.</div>
            </div>
            <button className="delete-button" onClick={() => { setNodes((current) => current.filter((node) => node.id !== selectedId)); setEdges((current) => current.filter((edge) => edge.source !== selectedId && edge.target !== selectedId)); setSelectedId(null); setNotice("Bloc supprimé du brouillon."); }}>Supprimer ce bloc</button>
          </> : <div className="inspector-empty"><span>◇</span><strong>Aucun bloc sélectionné</strong><p>Sélectionnez un bloc sur le canvas pour modifier ses paramètres.</p></div>}
        </aside>
      </div>
    </main>
  );
}
