import { useCallback, useEffect, useState } from "react";
import { ApiError, authApi, patientApi } from "@/api/client";
import type { Patient, PatientRegisterPayload, PatientUpdatePayload } from "@/types";

export function usePatient() {
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    let cancelled = false;
    localStorage.removeItem("auckland-hospital.patient");
    const expired = () => setPatient(null);
    window.addEventListener("health-auth-expired", expired);
    const restore = async () => {
      try {
        if (authApi.hasToken()) {
          const me = await authApi.me();
          if (me.role !== "patient") throw new Error("Patient role required");
          const own = await patientApi.me();
          if (!cancelled) setPatient(own);
        }
      } catch { authApi.logout(); }
      finally { if (!cancelled) setLoaded(true); }
    };
    void restore();
    return () => { cancelled = true; window.removeEventListener("health-auth-expired", expired); };
  }, []);
  const login = useCallback(async (username: string, password: string): Promise<{ ok: true } | { ok: false; status: number; message: string }> => {
    try {
      await authApi.login(username, password);
      if ((await authApi.me()).role !== "patient") throw new Error("A patient account is required");
      setPatient(await patientApi.me());
      return { ok: true };
    } catch (e) {
      authApi.logout();
      const err = e as ApiError;
      return { ok: false, status: err.status ?? 0, message: err.message };
    }
  }, []);
  const register = useCallback(async (_payload: PatientRegisterPayload): Promise<{ ok: false; status: number; message: string }> => (
    { ok: false, status: 403, message: "Contact the clinic to create a verified account" }
  ), []);
  const update = useCallback(async (payload: PatientUpdatePayload) => {
    if (!patient) return;
    const updated = await patientApi.update(patient.patient_id, payload);
    setPatient(updated); return updated;
  }, [patient]);
  const logout = useCallback(() => { authApi.logout(); setPatient(null); }, []);
  return { patient, loaded, login, register, update, logout };
}
