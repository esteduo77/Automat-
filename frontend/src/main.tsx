import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import Dashboard from "./Dashboard";
import "./styles.css";

const page = window.location.hash === "#editor" ? <App /> : <Dashboard />;

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>{page}</React.StrictMode>
);
