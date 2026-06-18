"use client";
import { useState } from "react";
import { api } from "@/lib/api";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Combobox } from "@/components/ui/combobox";
import type { CuentaOpcion } from "@/lib/types";

interface Props {
  open: boolean;
  tipo: string;
  onClose: () => void;
  onCreated: () => void;
  cuentasPago: CuentaOpcion[];
  cuentasGasto: CuentaOpcion[];
}

export function NuevoImpuestoDialog({ open, tipo, onClose, onCreated, cuentasPago, cuentasGasto }: Props) {
  const [codigo, setCodigo] = useState("");
  const [nombre, setNombre] = useState("");
  const [tarifa, setTarifa] = useState("0");
  const [cuentaCre, setCuentaCre] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const allCuentas = [...cuentasPago, ...cuentasGasto].map((c) => ({
    value: c.codigo,
    label: c.label ?? `${c.codigo} – ${c.nombre}`,
  }));

  const handleSave = async () => {
    if (!codigo.trim() || !cuentaCre) { setError("Código y cuenta crédito son obligatorios."); return; }
    setSaving(true);
    setError("");
    try {
      await api.crearImpuesto({
        codigo: codigo.trim(),
        nombre: nombre.trim() || undefined,
        tipo_impuesto: tipo,
        tarifa: parseFloat(tarifa) || 0,
        cta_compras: cuentaCre,
      });
      setCodigo(""); setNombre(""); setTarifa("0"); setCuentaCre("");
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    }
    setSaving(false);
  };

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Agregar código de impuesto</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 mt-2">
          <div className="inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold" style={{ backgroundColor: "var(--info-bg)", borderColor: "var(--info-border)", color: "var(--info-text)" }}>
            Tipo: {tipo}
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Código SIIGO *</Label>
              <Input value={codigo} onChange={(e) => setCodigo(e.target.value)} placeholder="ej. RETE1" />
            </div>
            <div className="space-y-1.5">
              <Label>Tarifa %</Label>
              <Input type="number" value={tarifa} onChange={(e) => setTarifa(e.target.value)} min="0" max="100" step="0.5" />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Nombre / descripción</Label>
            <Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="ej. Retefuente servicios 1%" />
          </div>
          <div className="space-y-1.5">
            <Label>Cuenta crédito (PUC) *</Label>
            <Combobox options={allCuentas} value={cuentaCre} onChange={setCuentaCre} placeholder="Buscar por código o nombre..." />
          </div>
          {error && <p className="text-sm text-red-400">{error}</p>}
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" onClick={onClose}>Cancelar</Button>
            <Button onClick={handleSave} disabled={saving}>{saving ? "Guardando..." : "Guardar"}</Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
