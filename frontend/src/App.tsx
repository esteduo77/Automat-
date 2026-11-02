import { useEffect, useState } from "react";
type Health = { status: string; service: string };
export default function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    fetch("/api/health").then((r) => { if (!r.ok) throw new Error(); return r.json() as Promise<Health>; })
      .then(setHealth).catch(() => setError("API non connectée. Démarrez le backend pour vérifier son état."));
  }, []);
  return <main className="shell">
    <header className="topbar"><div className="brand-mark">AH</div><div><p className="eyebrow">ESPACE D'AUTOMATISATION</p><h1>Automation Hub</h1></div><span className="version">v0.1.0</span></header>
    <section className="hero"><p className="eyebrow">VOTRE CENTRE DE PILOTAGE</p><h2>Les automatisations, <span>au même endroit.</span></h2>
      <p className="intro">Une base sécurisée pour connecter vos outils, préparer vos tâches et garder le contrôle sur chaque action.</p>
      <div className="status"><span className={health ? "dot online" : "dot"} />{health ? "API opérationnelle" : error || "Vérification de l'API…"}</div>
    </section>
    <section className="grid" aria-label="Modules">
      <article className="module"><div className="module-icon">✦</div><p className="eyebrow">MOTEUR IA</p><h3>OpenAI</h3><p>Compréhension des demandes et orchestration des tâches, côté serveur.</p><span className="tag">Socle préparé</span></article>
      <article className="module"><div className="module-icon">G</div><p className="eyebrow">INTÉGRATION</p><h3>Google Workspace</h3><p>Gmail, Drive et Calendar seront ajoutés avec des autorisations ciblées.</p><span className="tag muted">À venir</span></article>
      <article className="module"><div className="module-icon">▦</div><p className="eyebrow">INTÉGRATION</p><h3>Microsoft 365</h3><p>Outlook, OneDrive et Excel via Microsoft Graph.</p><span className="tag muted">À venir</span></article>
    </section>
    <footer>Automation Hub · Une action sensible ne sera jamais exécutée sans validation.</footer>
  </main>;
}
