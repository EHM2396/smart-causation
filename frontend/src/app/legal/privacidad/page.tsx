/**
 * Política de Privacidad y Tratamiento de Datos Personales.
 *
 * ⚠️ BORRADOR TÉCNICO. Refleja con exactitud lo que la plataforma hace hoy
 * (proveedores, flujos de datos, retención), pero debe ser revisado y firmado
 * por un abogado colombiano antes de publicarse en producción.
 *
 * Los valores entre corchetes en @/lib/legal deben completarse antes de publicar.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { Documento } from "@/components/legal/documento";
import { Callout, H2, H3, OL, P, Tabla, Term, UL } from "@/components/legal/prose";
import { NP as N, SECCIONES_PRIVACIDAD as SECCIONES } from "@/components/legal/secciones";
import { ENTIDAD, SUBENCARGADOS } from "@/lib/legal";

export const metadata: Metadata = {
  title: `Política de Privacidad — ${ENTIDAD.marca}`,
  description:
    "Cómo tratamos los datos personales en Ciolix: qué recolectamos, para qué, con quién los compartimos y cómo ejercer tus derechos.",
};

export default function PrivacidadPage() {
  return (
    <Documento
      titulo="Política de Privacidad y Tratamiento de Datos Personales"
      resumen={`Esta política explica qué datos personales tratamos en ${ENTIDAD.marca}, con qué finalidad, con quién los compartimos, durante cuánto tiempo los conservamos y cómo puedes ejercer tus derechos. Está redactada conforme a la Ley 1581 de 2012, el Decreto 1074 de 2015 y la Circular Única de la Superintendencia de Industria y Comercio.`}
      secciones={SECCIONES}
    >
      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="quienes-somos" num={N["quienes-somos"]}>
        Quiénes somos y a qué aplica esta política
      </H2>
      <P>
        <Term>{ENTIDAD.razonSocial}</Term>, sociedad constituida bajo las leyes de la República
        de Colombia, identificada con NIT {ENTIDAD.nit} y domiciliada en {ENTIDAD.direccion},{" "}
        {ENTIDAD.ciudad} ({ENTIDAD.pais}), es la titular de la plataforma{" "}
        <Term>{ENTIDAD.marca}</Term> (en adelante, la &ldquo;Plataforma&rdquo;).
      </P>
      <P>
        {ENTIDAD.marca} es un servicio de software en la nube que automatiza la causación
        contable: lee facturas electrónicas emitidas en Colombia, sugiere la clasificación
        contable de cada ítem según el PUC y genera archivos listos para importar en SIIGO.
      </P>
      <P>
        Esta política aplica a todos los datos personales que tratamos con ocasión del uso de la
        Plataforma, de nuestro sitio web y de nuestros canales de contacto y soporte.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="definiciones" num={N["definiciones"]}>
        Definiciones
      </H2>
      <UL>
        <li>
          <Term>Titular:</Term> la persona natural cuyos datos personales son objeto de
          tratamiento.
        </li>
        <li>
          <Term>Dato personal:</Term> cualquier información vinculada o que pueda asociarse a una
          persona natural determinada o determinable.
        </li>
        <li>
          <Term>Dato sensible:</Term> el que afecta la intimidad del titular o cuyo uso indebido
          puede generar discriminación (salud, origen étnico, convicciones religiosas, datos
          biométricos, entre otros).
        </li>
        <li>
          <Term>Responsable del tratamiento:</Term> quien decide sobre la finalidad y los medios
          del tratamiento.
        </li>
        <li>
          <Term>Encargado del tratamiento:</Term> quien trata datos personales por cuenta y
          siguiendo las instrucciones del responsable.
        </li>
        <li>
          <Term>Cliente:</Term> la persona natural o jurídica que contrata un plan de{" "}
          {ENTIDAD.marca} y carga información en la Plataforma.
        </li>
        <li>
          <Term>Autorización:</Term> el consentimiento previo, expreso e informado del titular
          para tratar sus datos personales.
        </li>
        <li>
          <Term>Transmisión:</Term> entrega de datos a un encargado para que los trate siguiendo
          nuestras instrucciones.
        </li>
        <li>
          <Term>Transferencia:</Term> entrega de datos a otro responsable que los trata de manera
          autónoma.
        </li>
      </UL>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="doble-rol" num={N["doble-rol"]}>
        Nuestro doble rol: responsable en unos casos, encargado en otros
      </H2>
      <P>
        Esta distinción determina a quién debes dirigirte para ejercer tus derechos, así que la
        explicamos con precisión.
      </P>

      <H3>{N["doble-rol"]}.1. Somos RESPONSABLES de los datos de la cuenta</H3>
      <P>
        Respecto de los datos de quien se registra y usa la Plataforma —nombre, correo
        electrónico, credenciales, datos de facturación y registros técnicos de uso— nosotros
        decidimos la finalidad y los medios. Somos el responsable del tratamiento y respondemos
        directamente ante ti.
      </P>

      <H3>{N["doble-rol"]}.2. Somos ENCARGADOS de los datos que el Cliente carga</H3>
      <P>
        Las facturas electrónicas que el Cliente sube contienen datos de sus proveedores y
        terceros: razón social, NIT o cédula, dirección, teléfono y correo. Cuando el proveedor es
        una persona natural, esa información es dato personal.
      </P>
      <P>
        Sobre esos datos, <Term>el Cliente es el responsable del tratamiento</Term> y{" "}
        {ENTIDAD.razonSocial} actúa únicamente como <Term>encargado</Term>: los tratamos por
        cuenta del Cliente, siguiendo sus instrucciones y con el único fin de prestar el servicio
        contratado. No los usamos para finalidades propias, no los vendemos y no los cedemos a
        terceros con fines comerciales.
      </P>
      <Callout titulo="Qué significa esto en la práctica">
        Si eres proveedor de una empresa que usa {ENTIDAD.marca} y quieres conocer, actualizar o
        suprimir tus datos, debes dirigirte a esa empresa, que es la responsable. Si nos escribes
        a nosotros, trasladaremos tu solicitud al Cliente correspondiente dentro de los dos (2)
        días hábiles siguientes y te informaremos a quién se remitió.
      </Callout>
      <P>
        El Cliente declara y garantiza que cuenta con la autorización o el fundamento legal
        necesario para cargar en la Plataforma los datos personales de terceros, y nos mantiene
        indemnes frente a reclamaciones derivadas del incumplimiento de esa obligación.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="principios" num={N["principios"]}>
        Principios que aplicamos
      </H2>
      <P>
        Tratamos los datos personales conforme a los principios del artículo 4 de la Ley 1581 de
        2012: legalidad, finalidad, libertad, veracidad, transparencia, acceso y circulación
        restringida, seguridad y confidencialidad. A ellos sumamos dos compromisos operativos
        concretos:
      </P>
      <UL>
        <li>
          <Term>Minimización:</Term> solo pedimos los datos indispensables para prestar el
          servicio. No solicitamos cédula, fecha de nacimiento ni dirección personal para abrir
          una cuenta.
        </li>
        <li>
          <Term>Aislamiento entre clientes:</Term> cada empresa registrada opera en un espacio de
          datos separado. Ningún cliente puede consultar las facturas, catálogos, proveedores ni
          el aprendizaje de otro.
        </li>
      </UL>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="que-datos" num={N["que-datos"]}>
        Qué datos tratamos
      </H2>

      <H3>{N["que-datos"]}.1. Datos de la cuenta (somos responsables)</H3>
      <Tabla
        headers={["Dato", "Origen", "Por qué lo necesitamos"]}
        rows={[
          ["Nombre completo", "Lo ingresas al registrarte", "Identificarte dentro de la Plataforma y en las comunicaciones"],
          ["Correo electrónico", "Lo ingresas al registrarte", "Autenticación, verificación de la cuenta, recuperación de contraseña y avisos del servicio"],
          ["Contraseña", "La defines al registrarte", "Se almacena cifrada con bcrypt. Nunca la conocemos ni la podemos recuperar en texto claro"],
          ["Nombre y NIT de la empresa", "Los ingresas al registrarte", "Crear el espacio de trabajo aislado y emitir la factura de la suscripción"],
        ]}
      />

      <H3>{N["que-datos"]}.2. Datos de facturación y pago</H3>
      <P>
        Para los planes pagos tratamos los datos necesarios para emitir la factura electrónica
        exigida por la DIAN: razón social, NIT, dirección, responsabilidades fiscales y correo de
        facturación. Los datos de la tarjeta o del medio de pago son capturados y almacenados
        directamente por la pasarela de pagos; {ENTIDAD.razonSocial} no los recibe ni los conserva.
      </P>

      <H3>{N["que-datos"]}.3. Datos técnicos y registros de seguridad</H3>
      <P>
        Registramos la dirección IP, el navegador y la fecha y hora de eventos relevantes
        —inicio de sesión, aceptación de estos documentos, errores del sistema— con el fin de
        proteger la cuenta, detectar accesos no autorizados y conservar prueba del consentimiento.
        No usamos estos registros para elaborar perfiles publicitarios.
      </P>

      <H3>{N["que-datos"]}.4. Datos contenidos en las facturas (somos encargados)</H3>
      <P>
        Al procesar los archivos XML de facturación electrónica tratamos, por cuenta del Cliente:
        identificación y razón social del proveedor, dirección, teléfono, correo, descripción de
        los ítems, valores, impuestos y la clasificación contable resultante.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="no-recolectamos" num={N["no-recolectamos"]}>
        Qué NO recolectamos
      </H2>
      <P>Lo decimos de forma expresa porque delimita el alcance de esta política:</P>
      <UL>
        <li>
          <Term>No tratamos datos sensibles.</Term> El servicio no los requiere y no hay campo
          alguno destinado a capturarlos.
        </li>
        <li>
          <Term>No solicitamos tus credenciales de la DIAN ni de tu ERP.</Term> Tú cargas los
          archivos manualmente y descargas el resultado. No accedemos a esos sistemas en tu
          nombre.
        </li>
        <li>
          <Term>No usamos cookies de rastreo, publicidad ni analítica de terceros.</Term> Ver la
          sección {N["cookies"]}.
        </li>
        <li>
          <Term>No compramos ni vendemos bases de datos personales</Term>, ni cedemos tus datos a
          terceros con fines comerciales o publicitarios.
        </li>
      </UL>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="finalidades" num={N["finalidades"]}>
        Para qué usamos los datos
      </H2>
      <P>Tratamos los datos personales exclusivamente para las siguientes finalidades:</P>
      <OL>
        <li>Crear, administrar y autenticar tu cuenta y el espacio de trabajo de tu empresa.</li>
        <li>
          Prestar el servicio contratado: leer facturas, sugerir clasificación contable, generar
          los archivos de exportación y conservar el historial de causaciones.
        </li>
        <li>
          Mejorar la precisión de las sugerencias <Term>dentro de tu propia empresa</Term>,
          aprendiendo de las decisiones que confirmas. Este aprendizaje no se comparte entre
          clientes.
        </li>
        <li>
          Enviar comunicaciones transaccionales indispensables: verificación de correo,
          recuperación de contraseña, avisos de facturación, cambios en estos documentos e
          incidentes de seguridad.
        </li>
        <li>Atender peticiones, quejas, reclamos y solicitudes de soporte.</li>
        <li>Emitir la factura electrónica de la suscripción y gestionar el recaudo.</li>
        <li>
          Prevenir fraude, uso no autorizado y abuso de la Plataforma, y garantizar su seguridad.
        </li>
        <li>Cumplir obligaciones legales, contables, tributarias y requerimientos de autoridad competente.</li>
        <li>
          Elaborar estadísticas agregadas y anonimizadas sobre el uso de la Plataforma, de las que
          no es posible identificar a ninguna persona ni empresa.
        </li>
      </OL>
      <P>
        El envío de comunicaciones comerciales o promocionales requiere tu autorización
        independiente y podrás retirarla en cualquier momento desde el enlace incluido en cada
        mensaje, sin que ello afecte la prestación del servicio.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="bases-juridicas" num={N["bases-juridicas"]}>
        Qué legitima cada tratamiento
      </H2>
      <P>
        En Colombia la regla general es la autorización previa, expresa e informada del titular
        (artículo 9 de la Ley 1581 de 2012). Junto a ella, el artículo 10 exceptúa de ese
        requisito algunos supuestos. Detallamos en qué se apoya cada tratamiento para que puedas
        saber, en concreto, cuáles puedes revocar y cuáles no.
      </P>
      <Tabla
        headers={["Tratamiento", "En qué se apoya", "¿Puedes revocarlo?"]}
        rows={[
          [
            "Crear y operar tu cuenta; prestar el servicio contratado",
            "Ejecución del contrato que celebras al aceptar los Términos, además de tu autorización",
            "Sí, cancelando el servicio: sin este tratamiento no hay plataforma que prestar",
          ],
          [
            <>Transmisión de datos a los proveedores del exterior (sección {N["terceros"]})</>,
            "Tu autorización expresa e inequívoca (art. 26, lit. a)",
            "Sí, escribiéndonos. Implica desactivar la asistencia por IA",
          ],
          [
            "Correos transaccionales (verificación, contraseña, avisos del servicio)",
            "Ejecución del contrato y deber de información",
            "No mientras la cuenta esté activa: son indispensables para operarla",
          ],
          [
            "Facturación electrónica y conservación de soportes contables",
            "Cumplimiento de un deber legal (Estatuto Tributario y normas contables)",
            "No: la ley nos obliga a conservarlos",
          ],
          [
            "Registros técnicos y de seguridad; prevención de fraude",
            "Ejecución del contrato y deber legal de adoptar medidas de seguridad (art. 4, lit. g)",
            "No mientras la cuenta esté activa",
          ],
          [
            "Comunicaciones comerciales y promocionales",
            "Autorización independiente y opcional",
            "Sí, en cualquier momento y sin afectar el servicio",
          ],
          [
            "Estadísticas agregadas y anonimizadas",
            "No aplica: al anonimizarse de forma irreversible dejan de ser datos personales",
            "No aplica",
          ],
        ]}
      />
      <P>
        Respecto de los datos de terceros que el Cliente carga, la base la determina el propio
        Cliente en su condición de responsable; nosotros los tratamos por instrucción suya, según
        se explica en la sección {N["doble-rol"]}.
      </P>
      <Callout titulo="Sobre el «interés legítimo»">
        Lo mencionamos porque suele aparecer en políticas traducidas del reglamento europeo: el
        interés legítimo <Term>no es una base autónoma de tratamiento</Term> en el régimen
        colombiano. No lo invocamos, y ningún tratamiento descrito aquí se apoya en él.
      </Callout>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="ia" num={N["ia"]}>
        Uso de inteligencia artificial
      </H2>
      <P>
        La Plataforma usa un modelo de lenguaje de <Term>OpenAI, L.L.C.</Term> (Estados Unidos)
        para sugerir la cuenta contable y el código de impuesto de cada ítem de factura. Por
        transparencia, detallamos exactamente cómo funciona.
      </P>

      <H3>{N["ia"]}.1. Qué se envía al modelo</H3>
      <UL>
        <li>
          La <Term>descripción del ítem</Term> de la factura, depurada previamente de forma
          automática: los NIT, números de teléfono, correos electrónicos e importes monetarios se
          reemplazan por marcadores neutros antes del envío, y el texto se trunca a 300
          caracteres.
        </li>
        <li>
          El <Term>nombre o razón social del proveedor</Term> y su tipo. Este dato se envía sin
          depurar, porque es determinante para acertar la clasificación. Cuando el proveedor es
          una persona natural, constituye un dato personal.
        </li>
        <li>
          El catálogo de cuentas PUC y códigos de impuesto de tu empresa, y hasta veinticinco
          decisiones previas tuyas usadas como ejemplo.
        </li>
      </UL>

      <H3>{N["ia"]}.2. Qué NO se envía al modelo</H3>
      <UL>
        <li>Tu nombre, tu correo, tus credenciales ni los datos de tu cuenta.</li>
        <li>El archivo XML completo de la factura.</li>
        <li>Los importes, totales e impuestos liquidados de la factura.</li>
        <li>Datos de otras empresas o de otros clientes de la Plataforma.</li>
      </UL>

      <H3>{N["ia"]}.3. Compromisos sobre el modelo</H3>
      <UL>
        <li>
          <Term>Tus datos no se usan para entrenar modelos.</Term> Utilizamos la API de OpenAI,
          cuyos términos para clientes de API establecen que el contenido enviado no se emplea
          para entrenar ni mejorar sus modelos.
        </li>
        <li>
          <Term>No hay decisiones automatizadas con efectos jurídicos.</Term> La salida del modelo
          es una <em>sugerencia</em>. Ninguna causación se registra sin que una persona la revise
          y la confirme expresamente en la Plataforma.
        </li>
        <li>
          Puedes solicitar la <Term>desactivación de la asistencia por IA</Term> para tu empresa
          escribiendo a {ENTIDAD.emailDatos}. La Plataforma seguirá operando con la clasificación
          basada en reglas y en tu histórico.
        </li>
        <li>
          <Term>Las sugerencias no son deterministas ni estables en el tiempo.</Term> Una misma
          descripción puede recibir sugerencias distintas en momentos distintos, porque el
          proveedor actualiza sus modelos, porque tu catálogo de cuentas cambia o porque el
          histórico de decisiones de tu empresa evolucionó. Esto es inherente a la tecnología y no
          constituye una falla del servicio.
        </li>
      </UL>

      <Callout titulo="La sugerencia no es asesoría contable ni tributaria">
        {ENTIDAD.marca} es una herramienta de apoyo. La responsabilidad profesional sobre la
        clasificación contable, la liquidación de impuestos y el cumplimiento de las obligaciones
        ante la DIAN es y sigue siendo del Cliente y del contador que firma. Revisa siempre las
        sugerencias antes de confirmarlas.
      </Callout>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="terceros" num={N["terceros"]}>
        Terceros que acceden a los datos y transferencias internacionales
      </H2>
      <P>
        Para operar la Plataforma nos apoyamos en los proveedores que se listan a continuación.
        Todos actúan como encargados, están obligados contractualmente a la confidencialidad y
        solo pueden tratar los datos para la finalidad indicada.
      </P>
      <Tabla
        headers={["Proveedor", "Para qué", "País", "Nivel adecuado"]}
        rows={SUBENCARGADOS.map((s) => [
          s.nombre,
          s.finalidad,
          s.pais,
          s.adecuado === null ? "Según región contratada" : s.adecuado ? "Sí" : "No",
        ])}
      />
      <P>
        Algunos de estos proveedores están ubicados en <Term>Estados Unidos</Term>, país que no
        figura en el listado de países con nivel adecuado de protección de la Circular Externa 005
        de 2017 de la Superintendencia de Industria y Comercio. Conforme al artículo 26, literal
        a), de la Ley 1581 de 2012, esa transmisión se ampara en{" "}
        <Term>tu autorización expresa e inequívoca</Term>, que otorgas al aceptar esta política al
        registrarte.
      </P>
      <H3>Garantías exigidas a estos proveedores</H3>
      <P>
        La autorización no es lo único en lo que nos apoyamos. Con cada proveedor que accede a
        datos personales exigimos, como condición para contratarlo:
      </P>
      <UL>
        <li>
          <Term>Compromiso contractual de tratamiento limitado:</Term> solo pueden tratar los datos
          para la finalidad que les instruimos, nunca para fines propios.
        </li>
        <li>
          <Term>Obligación de confidencialidad</Term> extensiva a su personal y a sus propios
          subcontratistas.
        </li>
        <li>
          <Term>Medidas técnicas de seguridad</Term> equivalentes o superiores a las descritas en
          la sección {N["seguridad"]}: cifrado en tránsito, control de acceso y trazabilidad.
        </li>
        <li>
          <Term>Deber de notificarnos</Term> cualquier incidente de seguridad que afecte los datos
          que les transmitimos.
        </li>
        <li>
          <Term>Devolución o supresión</Term> de los datos al terminar la relación.
        </li>
      </UL>
      <P>
        Antes de incorporar un proveedor nuevo que vaya a acceder a datos personales, verificamos
        que cumpla estas condiciones y actualizamos la tabla anterior.
      </P>
      <P>
        Si no deseas autorizar la transmisión a Estados Unidos, no podremos ofrecerte la
        asistencia por inteligencia artificial. Escríbenos a {ENTIDAD.emailDatos} para evaluar
        alternativas.
      </P>
      <P>
        Además, podremos revelar datos personales cuando lo exija una autoridad judicial o
        administrativa competente, en ejercicio de sus funciones legales, o cuando sea necesario
        para ejercer o defender un derecho en un proceso.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="cookies" num={N["cookies"]}>
        Cookies y almacenamiento local
      </H2>
      <P>
        <Term>{ENTIDAD.marca} no utiliza cookies.</Term> Tampoco usamos píxeles de seguimiento,
        herramientas de analítica web, redes publicitarias ni tecnologías de terceros que
        registren tu comportamiento de navegación.
      </P>
      <P>
        Lo único que guardamos en tu dispositivo es <Term>almacenamiento local</Term> (
        <code>localStorage</code>) estrictamente necesario para que la aplicación funcione:
      </P>
      <Tabla
        headers={["Clave", "Qué guarda", "Duración"]}
        rows={[
          [
            "smart-causacion-auth",
            "Tu sesión iniciada (token de acceso y empresa activa), para que no tengas que autenticarte en cada pantalla",
            "Hasta que cierras sesión o expira el token",
          ],
          [
            "theme",
            "Si prefieres el tema claro u oscuro",
            "Hasta que la borres desde tu navegador",
          ],
        ]}
      />
      <P>
        Al tratarse de almacenamiento estrictamente necesario para prestar un servicio que
        solicitaste expresamente, no requiere un banner de consentimiento. Puedes eliminarlo en
        cualquier momento desde la configuración de tu navegador; si lo haces, se cerrará tu
        sesión.
      </P>
      <Callout titulo="Si esto cambia en el futuro">
        Si llegamos a incorporar analítica, medición o publicidad —Google Analytics, Meta Pixel,
        Hotjar, Clarity o similares—, antes de activarlas: publicaremos una Política de Cookies
        independiente con el detalle de cada una, mostraremos un banner de consentimiento previo
        con opción de rechazar, y no instalaremos nada distinto de lo estrictamente necesario
        hasta que aceptes. Mientras esta sección diga que no usamos cookies, es porque no las
        usamos.
      </Callout>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="conservacion" num={N["conservacion"]}>
        Conservación y supresión
      </H2>
      <Tabla
        headers={["Información", "Cuánto la conservamos"]}
        rows={[
          ["Datos de la cuenta", "Mientras la cuenta esté activa y hasta 30 días después de su cancelación"],
          [
            "Facturas cargadas, causaciones e historial",
            "Mientras la cuenta esté activa. Tras la cancelación, 30 días para que puedas exportarlos; luego se eliminan",
          ],
          [
            "Prueba de aceptación de los documentos legales",
            "Cinco (5) años desde la terminación de la relación, como respaldo de la autorización",
          ],
          [
            "Facturas de la suscripción y soportes contables",
            "Diez (10) años, conforme al artículo 28 de la Ley 962 de 2005 y el artículo 632 del Estatuto Tributario",
          ],
          ["Registros técnicos y de seguridad", "Doce (12) meses"],
        ]}
      />
      <H3>Cómo se elimina</H3>
      <P>
        Cumplido el plazo, los datos se eliminan mediante procedimientos que impiden su
        reconstrucción, o se anonimizan de forma irreversible cuando queremos preservar el valor
        estadístico del registro. La eliminación alcanza también las copias que existan en los
        sistemas de nuestros proveedores, a quienes instruimos en ese sentido.
      </P>
      <P>
        Conservamos únicamente aquellos datos respecto de los cuales exista un deber legal de
        retención, o que sean necesarios para atender una reclamación, una investigación o un
        proceso en curso. En ese caso se conservan bloqueados: solo accesibles para atender ese
        fin concreto, y se suprimen en cuanto deja de existir.
      </P>
      <P>
        Dejamos constancia de las supresiones realizadas para poder acreditarlas si un titular o
        una autoridad lo solicita.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="seguridad" num={N["seguridad"]}>
        Seguridad e incidentes
      </H2>
      <UL>
        <li>Todo el tráfico viaja cifrado mediante HTTPS con certificados renovados automáticamente.</li>
        <li>Las contraseñas se almacenan con bcrypt y salt individual; no son reversibles.</li>
        <li>
          El acceso se controla mediante tokens firmados con expiración, y la sesión se cierra
          automáticamente tras diez minutos de inactividad.
        </li>
        <li>
          La base de datos no está expuesta a internet: solo es accesible desde la propia
          aplicación.
        </li>
        <li>
          Cada empresa está aislada a nivel de datos: toda consulta se filtra por el identificador
          de empresa del usuario autenticado.
        </li>
        <li>
          El texto que se envía al modelo de inteligencia artificial se depura automáticamente de
          identificadores, teléfonos, correos e importes, y se descartan las entradas que
          contengan intentos de manipulación del modelo.
        </li>
        <li>El personal con acceso a datos está sujeto a deberes de confidencialidad.</li>
      </UL>
      <H3>Gestión de incidentes</H3>
      <P>
        Ninguna medida de seguridad es infalible. Contamos con un protocolo interno de gestión de
        incidentes que, ante un evento que comprometa datos personales, contempla:
      </P>
      <OL>
        <li>contener el incidente y detener la exposición;</li>
        <li>
          evaluar qué datos y qué titulares resultaron afectados, y si el Cliente actúa como
          responsable de esos datos;
        </li>
        <li>
          notificar a los titulares afectados y, cuando actuemos como encargados, al Cliente
          responsable, para que pueda cumplir sus propios deberes de notificación;
        </li>
        <li>
          reportar a la Superintendencia de Industria y Comercio en los términos y plazos exigidos
          por la normativa vigente;
        </li>
        <li>documentar el incidente y adoptar las medidas correctivas que impidan su repetición.</li>
      </OL>
      <P>
        Los plazos concretos de cada paso se rigen por la normativa aplicable en el momento del
        incidente, y no por lo que aquí se enuncie: esta sección describe el procedimiento, no
        sustituye la obligación legal.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="derechos" num={N["derechos"]}>
        Tus derechos y cómo ejercerlos
      </H2>
      <P>Como titular de datos personales tienes derecho a:</P>
      <OL>
        <li>Conocer, actualizar y rectificar tus datos personales.</li>
        <li>Solicitar prueba de la autorización que otorgaste.</li>
        <li>Ser informado sobre el uso que hemos dado a tus datos.</li>
        <li>
          Revocar la autorización y solicitar la supresión de tus datos, cuando no exista un deber
          legal o contractual que obligue a conservarlos.
        </li>
        <li>Acceder de forma gratuita a los datos que hayan sido objeto de tratamiento.</li>
        <li>
          Presentar quejas ante la Superintendencia de Industria y Comercio por infracciones a la
          Ley 1581 de 2012.
        </li>
      </OL>

      <H3>Área responsable de la atención</H3>
      <P>
        La atención de consultas y reclamos sobre datos personales está a cargo del{" "}
        <Term>Área de Protección de Datos Personales</Term> de {ENTIDAD.razonSocial}, dependencia
        designada internamente para esta función y que recibe las solicitudes en{" "}
        <Term>{ENTIDAD.emailDatos}</Term>.
      </P>
      <P>
        Esa área es la única facultada para tramitar el ejercicio de derechos, lleva el registro
        de las solicitudes recibidas y de su respuesta, y es la responsable de mantener
        actualizada esta política. Es un canal distinto del de soporte comercial: si escribes a{" "}
        {ENTIDAD.emailSoporte} sobre un asunto de habeas data, tu solicitud se trasladará
        internamente, pero el plazo de respuesta corre desde que llega al canal correcto.
      </P>

      <H3>Procedimiento</H3>
      <P>
        Escribe a <Term>{ENTIDAD.emailDatos}</Term> indicando tu nombre e identificación, una
        descripción clara de tu solicitud, la dirección física o electrónica donde quieres recibir
        la respuesta y los documentos que quieras hacer valer.
      </P>
      <Tabla
        headers={["Tipo de solicitud", "Plazo de respuesta", "Prórroga"]}
        rows={[
          ["Consulta", "10 días hábiles", "Hasta 5 días hábiles adicionales, informándote los motivos"],
          ["Reclamo", "15 días hábiles", "Hasta 8 días hábiles adicionales, informándote los motivos"],
        ]}
      />
      <P>
        Si el reclamo está incompleto, te lo haremos saber dentro de los cinco (5) días hábiles
        siguientes para que lo completes. Si transcurridos dos (2) meses no recibimos la
        información solicitada, entenderemos que has desistido.
      </P>
      <P>
        Antes de presentar una queja ante la Superintendencia de Industria y Comercio debes
        haber agotado la consulta o el reclamo directo ante nosotros. Es lo que la ley denomina{" "}
        <Term>requisito de procedibilidad</Term>.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="autorizacion" num={N["autorizacion"]}>
        Qué declaras al aceptar esta política
      </H2>
      <P>Al marcar la casilla de aceptación durante el registro, declaras que:</P>
      <OL>
        <li>
          Eres mayor de edad y tienes capacidad legal para obligarte; y si actúas en nombre de una
          empresa, que cuentas con facultades suficientes para representarla.
        </li>
        <li>
          Autorizas de manera previa, expresa e informada el tratamiento de tus datos personales
          para las finalidades descritas en la sección {N["finalidades"]}.
        </li>
        <li>
          Autorizas de manera <Term>expresa e inequívoca</Term> la transmisión de datos a los
          proveedores listados en la sección {N["terceros"]}, incluidos los ubicados en Estados Unidos.
        </li>
        <li>
          Fuiste informado de que no estás obligado a autorizar el tratamiento de datos sensibles
          y de que la Plataforma no los solicita.
        </li>
        <li>
          Conoces tus derechos como titular y los mecanismos para ejercerlos descritos en la
          sección {N["derechos"]}.
        </li>
        <li>
          Si cargas datos personales de terceros, cuentas con la autorización o el fundamento
          legal para hacerlo y asumes la condición de responsable respecto de ellos.
        </li>
      </OL>
      <P>
        Conservamos como prueba de esta autorización la fecha y hora, la versión del documento
        aceptado, tu dirección IP y el navegador utilizado.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="menores" num={N["menores"]}>
        Menores de edad
      </H2>
      <P>
        La Plataforma está dirigida exclusivamente a personas mayores de edad en ejercicio de una
        actividad profesional o empresarial. No recolectamos de forma consciente datos de menores
        de edad. Si detectamos que se registró un menor, suprimiremos la cuenta y sus datos.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="cambios" num={N["cambios"]}>
        Cambios en esta política
      </H2>
      <P>
        Podemos actualizar esta política para reflejar cambios en el servicio o en la normativa.
        Cada versión lleva número y fecha de vigencia visibles al inicio del documento. Cuando el
        cambio sea sustancial —nuevas finalidades, nuevos proveedores con acceso a datos o nuevas
        transferencias internacionales— te lo notificaremos por correo electrónico con al menos
        quince (15) días calendario de antelación y solicitaremos nuevamente tu autorización.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="contacto" num={N["contacto"]}>
        Contacto, registro de bases de datos y autoridad de control
      </H2>
      <P>
        <Term>Responsable:</Term> {ENTIDAD.razonSocial} — NIT {ENTIDAD.nit}
        <br />
        <Term>Dirección:</Term> {ENTIDAD.direccion}, {ENTIDAD.ciudad}, {ENTIDAD.pais}
        <br />
        <Term>Área de Protección de Datos:</Term> {ENTIDAD.emailDatos}
        <br />
        <Term>Soporte y PQRS:</Term> {ENTIDAD.emailSoporte}
        <br />
        <Term>Teléfono:</Term> {ENTIDAD.telefono}
      </P>

      <H3>Registro Nacional de Bases de Datos</H3>
      <P>
        Las bases de datos personales que administramos y que estén sujetas a la obligación de
        inscripción en el <Term>Registro Nacional de Bases de Datos (RNBD)</Term> de la
        Superintendencia de Industria y Comercio se registran y se mantienen actualizadas conforme
        al Decreto 1074 de 2015 y a la Circular Única de esa entidad, incluida la actualización
        anual y el reporte de novedades y de reclamos.
      </P>

      <H3>Autoridad de control</H3>
      <P>
        La autoridad de control en materia de protección de datos personales en Colombia es la{" "}
        <Term>Superintendencia de Industria y Comercio</Term>, Delegatura para la Protección de
        Datos Personales. Puedes acudir a ella una vez agotado el trámite previo ante nosotros
        descrito en la sección {N["derechos"]}.
      </P>

      <div
        className="mt-14 border-t pt-6 text-sm"
        style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)" }}
      >
        Consulta también nuestros{" "}
        <Link href="/legal/terminos" style={{ color: "var(--brand)" }}>
          Términos y Condiciones
        </Link>
        .
      </div>
    </Documento>
  );
}
