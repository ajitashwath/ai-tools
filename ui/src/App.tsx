import { BrowserRouter as Router, Route, Routes } from "react-router-dom";
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
