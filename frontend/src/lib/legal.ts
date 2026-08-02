/**
 * Datos de la entidad y versionado de los documentos legales.
 *
 * ⚠️ ÚNICO lugar donde se editan estos valores. Las páginas /legal/terminos y
 * /legal/privacidad los consumen, y VERSION_LEGAL se guarda en la tabla
 * `consentimientos` cada vez que un usuario acepta al registrarse.
 *
 * Si cambia el contenido de los documentos de forma sustancial, sube VERSION_LEGAL
 * y actualiza FECHA_VIGENCIA: los consentimientos previos quedan asociados a la
 * versión antigua, que es exactamente lo que se necesita como prueba.
 */

export const VERSION_LEGAL = "1.0";
export const FECHA_VIGENCIA = "1 de agosto de 2026";

export const ENTIDAD = {
  /** Marca comercial del producto. */
  marca: "Ciolix",
  /** Razón social de la sociedad titular de la plataforma. */
  razonSocial: "[RAZÓN SOCIAL] S.A.S.",
  nit: "[NIT con dígito de verificación]",
  direccion: "[Dirección de notificaciones]",
  ciudad: "[Ciudad]",
  pais: "Colombia",
  /** Canal para PQRS y soporte comercial. */
  emailSoporte: "[soporte@dominio.com]",
  /** Canal exclusivo para el ejercicio de derechos de habeas data. */
  emailDatos: "[protecciondedatos@dominio.com]",
  telefono: "[+57 ...]",
  /** URL pública donde se publican planes y tarifas vigentes. */
  urlPlanes: "/planes",
} as const;

/**
 * Terceros que acceden a datos en la prestación del servicio.
 * `adecuado` = el país cuenta con nivel adecuado de protección según la
 * Circular Externa 005 de 2017 de la SIC. Si es false, la transferencia
 * requiere autorización expresa e inequívoca del titular
 * (art. 26 lit. a, Ley 1581 de 2012).
 */
export const SUBENCARGADOS = [
  {
    nombre: "Oracle Cloud Infrastructure",
    finalidad: "Alojamiento de la aplicación y de la base de datos",
    pais: "[Región contratada]",
    adecuado: null,
  },
  {
    nombre: "Vercel Inc.",
    finalidad: "Alojamiento y entrega de la interfaz web",
    pais: "Estados Unidos",
    adecuado: false,
  },
  {
    nombre: "OpenAI, L.L.C.",
    finalidad: "Sugerencia automatizada de clasificación contable",
    pais: "Estados Unidos",
    adecuado: false,
  },
  {
    nombre: "Hostinger International Ltd.",
    finalidad: "Envío de correo transaccional (verificación, recuperación de clave)",
    pais: "Lituania (Unión Europea)",
    adecuado: true,
  },
] as const;
