import { useEffect, useState } from "react";
import "./dashboard.css";

const API_BASE = window.location.hostname === "localhost" ? "" : "https://automat-api.onrender.com";

type Workflow = { id: string; name: string; updated_at?: string; created_at?: string };

export default function Dashboard() {
  const [apiState, setApiState] = useState<"checking" | "online" | "offline">("checking");
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [accountConnected, setAccountConnected] = useState(false);

  useEffect(() => {
    let active = true;
    fetch(API_BASE + "/api/health")
      .then((response) => {
        if (!response.ok) throw new Error("API indisponible");
        if (active) setApiState("online");
      })
      .catch(() => { if (active) setApiState("offline"); });

    const token = window.localStorage.getItem("automation-hub-token");
    if (token) {
      fetch(API_BASE + "/api/workflows", { headers: { Authorization: "Bearer " + token } })
        .then((response) => {
          if (!response.ok) throw new Error("Connexion requise");
          return response.json();
        })
        .then((data: Workflow[]) => {
          if (active) { setWorkflows(Array.isArray(data) ? data : []); setAccountConnected(true); }
        })
        .catch(() => { if (active) setAccountConnected(false); });
    }
    return () => { active = false; };
  }, []);

  return (
    <main className="dashboard-shell">
      <aside className="dashboard-sidebar">
        <a className="dashboard-brand" href="/">
          <span className="brand-mark">AH</span>
          <span><strong>Automation Hub</strong><small>VOTRE ESPACE AUTOMATISATION</small></span>
        </a>
        <div className="sidebar-label">ESPACE DE TRAVAIL</div>
        <a className="sidebar-link active" href="/"> <span>▦</span> Vue d’ensemble</a>
        <a className="sidebar-link" href="/#editor"><span>⌘</span> Éditeur de workflows</a>
        <a className="sidebar-link" href={API_BASE + "/docs"} target="_blank" rel="noreferrer"><span>⌁</span> Documentation API</a>
        <div className="sidebar-bottom">
          <div className="sidebar-label">ÉTAT DU SERVICE</div>
          <div className="service-indicator"><i className={apiState === "online" ? "online" : apiState === "offline" ? "offline" : ""} />{apiState === "online" ? "API opérationnelle" : apiState === "offline" ? "API indisponible" : "Vérification…"}</div>
          <small>Automation Hub · Version 0.4.0</small>
        </div>
      </aside>

      <section className="dashboard-main">
        <header className="dashboard-topbar">
          <div><span className="dashboard-kicker">TABLEAU DE BORD</span><strong>Vue d’ensemble</strong></div>
          <a className="dashboard-avatar" href="/#editor" aria-label="Ouvrir l’espace utilisateur">AH</a>
        </header>

        <div className="dashboard-content">
          <section className="welcome-panel">
            <div className="welcome-copy">
              <span className="welcome-tag">AUTOMATISEZ EN TOUTE SIMPLICITÉ</span>
              <h1>Bonjour et bienvenue sur <em>Automation Hub.</em></h1>
              <p>Créez des workflows, connectez vos outils et gardez le contrôle sur chaque automatisation.</p>
              <a className="primary-cta" href="/#editor">Ouvrir l’éditeur <span>→</span></a>
            </div>
            <div className="welcome-art" aria-hidden="true">
              <div className="orbit orbit-one" /><div className="orbit orbit-two" />
              <div className="hub-core"><span>AH</span><small>HUB</small></div>
              <span className="orbit-node node-one">✦</span><span className="orbit-node node-two">↗</span><span className="orbit-node node-three">✓</span>
            </div>
          </section>

          <div className="section-heading"><div><span className="dashboard-kicker">VOTRE ACTIVITÉ</span><h2>En un coup d’œil</h2></div></div>
          <section className="dashboard-stats">
            <article className="stat-card"><div className="stat-icon mint">⌘</div><span>Workflows enregistrés</span><strong>{accountConnected ? workflows.length : "—"}</strong><small>{accountConnected ? "Dans votre espace" : "Connectez-vous pour consulter vos workflows"}</small></article>
            <article className="stat-card"><div className="stat-icon blue">◉</div><span>État de l’API</span><strong className={apiState === "online" ? "status-good" : apiState === "offline" ? "status-bad" : ""}>{apiState === "online" ? "En ligne" : apiState === "offline" ? "Hors ligne" : "…"}</strong><small>Vérification en direct du serveur</small></article>
            <article className="stat-card"><div className="stat-icon violet">⛨</div><span>Contrôle des actions</span><strong>Activé</strong><small>Validation humaine côté serveur pour les écritures externes</small></article>
          </section>

          <div className="section-heading"><div><span className="dashboard-kicker">POUR COMMENCER</span><h2>Votre espace de travail</h2></div></div>
          <section className="quick-actions">
            <a className="action-card" href="/#editor"><span className="action-symbol">＋</span><span><strong>Créer un workflow</strong><small>Assemblez des blocs et définissez vos automatisations.</small></span><b>→</b></a>
            <a className="action-card" href="/#editor"><span className="action-symbol">⌘</span><span><strong>Gérer mes workflows</strong><small>Retrouvez vos scénarios et modifiez leur logique.</small></span><b>→</b></a>
            <a className="action-card" href={API_BASE + "/docs"} target="_blank" rel="noreferrer"><span className="action-symbol">⌁</span><span><strong>Explorer l’API</strong><small>Consultez les routes techniques du backend.</small></span><b>↗</b></a>
          </section>

          <footer className="dashboard-footer"><span>Automation Hub <b>·</b> Conçu pour automatiser avec contrôle.</span><span>Version 0.4.0</span></footer>
        </div>
      </section>
    </main>
  );
}
