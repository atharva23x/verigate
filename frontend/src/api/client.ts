import axios from "axios";

// Local dev talks to the local backend; a deployed build talks to the
// Render API. Override both with VITE_API_URL at build time.
const API_URL =
  import.meta.env.VITE_API_URL ??
  (["localhost", "127.0.0.1"].includes(window.location.hostname)
    ? "http://localhost:8000"
    : "https://verigate-api.onrender.com");

export const api = axios.create({ baseURL: API_URL });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("verigate_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    if (error.response?.status === 401 && !window.location.pathname.includes("/login")) {
      localStorage.removeItem("verigate_token");
      localStorage.removeItem("verigate_user");
      window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

/** Fetch a protected image (page render / ELA heatmap) as an object URL. */
export async function fetchImageURL(path: string): Promise<string> {
  const res = await api.get(path, { responseType: "blob" });
  return URL.createObjectURL(res.data);
}

/** Download a protected file (audit CSV export). */
export async function downloadFile(path: string, filename: string) {
  const res = await api.get(path, { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const docTypeLabels: Record<string, string> = {
  EOA_FORM: "EoA Application Form",
  PREV_EOA_LETTER: "Previous EoA Letter",
  FIRE_SAFETY_NOC: "Fire & Safety NOC",
  BUILDING_STABILITY_CERT: "Building Stability Cert.",
  PREMISES_NOC: "Premises NOC",
  PHARMACY_REG_CERT: "PCI Registration Cert.",
  LAND_OWNERSHIP_DEED: "Land Ownership Deed",
  LEASE_DEED: "Campus Lease Deed",
  AFFIDAVIT_UNDERTAKING: "Affidavit of Undertaking",
};

export const stepLabels: Record<string, string> = {
  PREPROCESS: "Render pages",
  OCR: "OCR + extraction",
  FIELD_EXTRACTION: "Field extraction",
  RULE_CHECK: "APH 2024-27 checklist",
  ISSUER_CHECK: "Issuer portal check",
  TAMPER_DUPLICATE_CHECK: "ELA + pHash check",
  CONSISTENCY_CHECK: "XGBoost consistency",
  EVIDENCE_GATE: "Evidence Gate",
  FINALIZE: "Persist + audit",
};
