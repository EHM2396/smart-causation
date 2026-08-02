/**
 * Índice de secciones de los dos documentos legales, en un solo módulo.
 *
 * Vive aquí y no dentro de cada página porque los documentos se citan entre sí
 * ("ver la sección 9 de la Política de Privacidad"). Con los índices
 * centralizados, insertar una sección en un documento recalcula también las
 * referencias que el otro le hace.
 */
import { numeracion, type Seccion } from "@/components/legal/documento";

export const SECCIONES_PRIVACIDAD: Seccion[] = [
  { id: "quienes-somos", titulo: "Quiénes somos y a qué aplica" },
  { id: "definiciones", titulo: "Definiciones" },
  { id: "doble-rol", titulo: "Nuestro doble rol" },
  { id: "principios", titulo: "Principios que aplicamos" },
  { id: "que-datos", titulo: "Qué datos tratamos" },
  { id: "no-recolectamos", titulo: "Qué NO recolectamos" },
  { id: "finalidades", titulo: "Para qué usamos los datos" },
  { id: "bases-juridicas", titulo: "Qué legitima cada tratamiento" },
  { id: "ia", titulo: "Uso de inteligencia artificial" },
  { id: "terceros", titulo: "Terceros y transferencias" },
  { id: "cookies", titulo: "Cookies y almacenamiento local" },
  { id: "conservacion", titulo: "Conservación y supresión" },
  { id: "seguridad", titulo: "Seguridad e incidentes" },
  { id: "derechos", titulo: "Tus derechos y cómo ejercerlos" },
  { id: "autorizacion", titulo: "Qué declaras al aceptar" },
  { id: "menores", titulo: "Menores de edad" },
  { id: "cambios", titulo: "Cambios en esta política" },
  { id: "contacto", titulo: "Contacto, RNBD y autoridad de control" },
];

export const SECCIONES_TERMINOS: Seccion[] = [
  { id: "aceptacion", titulo: "Aceptación y capacidad" },
  { id: "definiciones", titulo: "Definiciones" },
  { id: "que-es", titulo: "Qué es y qué no es Ciolix" },
  { id: "ia", titulo: "Inteligencia artificial y responsabilidad" },
  { id: "cuenta", titulo: "Cuenta, credenciales y acceso" },
  { id: "planes", titulo: "Planes, límites y tarifas" },
  { id: "pago", titulo: "Pago, facturación y mora" },
  { id: "vigencia", titulo: "Vigencia, renovación y cancelación" },
  { id: "retracto", titulo: "Retracto y garantía del primer mes" },
  { id: "datos-cliente", titulo: "Propiedad de tus datos" },
  { id: "propiedad", titulo: "Propiedad intelectual y licencia" },
  { id: "obligaciones", titulo: "Obligaciones del Cliente" },
  { id: "prohibiciones", titulo: "Conductas prohibidas" },
  { id: "disponibilidad", titulo: "Disponibilidad, soporte y mantenimiento" },
  { id: "continuidad", titulo: "Continuidad, respaldos y fuerza mayor" },
  { id: "garantias", titulo: "Garantías y limitación de responsabilidad" },
  { id: "indemnidad", titulo: "Indemnidad" },
  { id: "confidencialidad", titulo: "Confidencialidad" },
  { id: "suspension", titulo: "Suspensión y terminación" },
  { id: "datos-personales", titulo: "Tratamiento de datos personales" },
  { id: "pqrs", titulo: "PQRS" },
  { id: "modificaciones", titulo: "Modificaciones" },
  { id: "ley", titulo: "Ley aplicable y conflictos" },
  { id: "varios", titulo: "Disposiciones varias" },
];

/** Número de sección por id. NP = privacidad, NT = términos. */
export const NP = numeracion(SECCIONES_PRIVACIDAD);
export const NT = numeracion(SECCIONES_TERMINOS);
