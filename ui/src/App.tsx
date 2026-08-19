import React, { useEffect, useState } from "react";
import { BrowserRouter as Router, Route, Routes, useNavigate } from "react-router-dom";
import "./App.css";

import TraceListPage from "./pages/TraceListPage";
import TraceDetailPage from "./pages/TraceDetailPage";

function App() {
  return (
    <Router>
      <div className="app">
        <Routes>
          <Route path="/" element={<TraceListPage />} />
          <Route path="/trace/:id" element={<TraceDetailPage />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;