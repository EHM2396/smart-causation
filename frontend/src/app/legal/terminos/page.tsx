/**
 * Términos y Condiciones de uso del SaaS.
 *
 * ⚠️ BORRADOR TÉCNICO. Refleja el funcionamiento real de la plataforma y el
 * modelo de negocio acordado, pero debe ser revisado y firmado por un abogado
 * colombiano antes de publicarse en producción.
 *
 * Los valores entre corchetes en @/lib/legal deben completarse antes de publicar.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { Documento } from "@/components/legal/documento";
import { Callout, H2, H3, OL, P, Tabla, Term, UL } from "@/components/legal/prose";
import { NP, NT as N, SECCIONES_TERMINOS as SECCIONES } from "@/components/legal/secciones";
import { ENTIDAD } from "@/lib/legal";

export const metadata: Metadata = {
  title: `Términos y Condiciones — ${ENTIDAD.marca}`,
  description:
    "Condiciones de uso del servicio Ciolix: planes, pagos, cancelación, responsabilidad y propiedad de los datos.",
};

export default function TerminosPage() {
  return (
    <Documento
      titulo="Términos y Condiciones"
      resumen={`Este documento regula la relación entre ${ENTIDAD.razonSocial} y quienes usan ${ENTIDAD.marca}. Explica qué incluye el servicio, cómo se cobra, cómo se cancela, de quién son los datos y hasta dónde llega nuestra responsabilidad. Es un contrato vinculante: léelo antes de aceptarlo.`}
      secciones={SECCIONES}
    >
      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="aceptacion" num={N["aceptacion"]}>
        Aceptación y capacidad
      </H2>
      <P>
        Estos términos regulan el acceso y uso de <Term>{ENTIDAD.marca}</Term> (la
        &ldquo;Plataforma&rdquo;), servicio prestado por <Term>{ENTIDAD.razonSocial}</Term>,
        sociedad constituida bajo las leyes de la República de Colombia, identificada con NIT{" "}
        {ENTIDAD.nit} y domiciliada en {ENTIDAD.direccion}, {ENTIDAD.ciudad} (la
        &ldquo;Compañía&rdquo;).
      </P>
      <P>
        Al marcar la casilla de aceptación durante el registro, o al acceder o usar la Plataforma
        por cualquier medio, celebras un contrato vinculante con la Compañía y declaras que:
      </P>
      <OL>
        <li>Eres mayor de edad y tienes capacidad legal para obligarte.</li>
        <li>
          Si actúas en nombre de una persona jurídica, cuentas con facultades suficientes para
          obligarla. De no tenerlas, responderás personalmente por las obligaciones aquí
          contraídas.
        </li>
        <li>La información que suministras es veraz, completa y actualizada.</li>
        <li>
          Leíste y aceptas también nuestra{" "}
          <Link href="/legal/privacidad" style={{ color: "var(--brand)" }}>
            Política de Privacidad
          </Link>
          , que forma parte integral de este contrato.
        </li>
      </OL>
      <P>Si no estás de acuerdo con estos términos, no debes registrarte ni usar la Plataforma.</P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="definiciones" num={N["definiciones"]}>
        Definiciones
      </H2>
      <UL>
        <li>
          <Term>Cliente</Term> o <Term>Usuario:</Term> la persona natural o jurídica que se
          registra y usa la Plataforma.
        </li>
        <li>
          <Term>Plan:</Term> la modalidad de suscripción contratada, que determina los límites de
          uso.
        </li>
        <li>
          <Term>Causación:</Term> el procesamiento de una factura electrónica dentro de la
          Plataforma hasta obtener su clasificación contable.
        </li>
        <li>
          <Term>Contenido del Cliente:</Term> los archivos, catálogos, facturas y demás
          información que el Cliente carga o genera en la Plataforma.
        </li>
        <li>
          <Term>Tarifa:</Term> el precio de la suscripción según el Plan contratado.
        </li>
        <li>
          <Term>Ciclo de facturación:</Term> el período mensual o anual por el cual se paga la
          suscripción.
        </li>
      </UL>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="que-es" num={N["que-es"]}>
        Qué es y qué no es {ENTIDAD.marca}
      </H2>
      <P>
        {ENTIDAD.marca} es un servicio de software como servicio (SaaS) que permite cargar
        facturas electrónicas emitidas en Colombia, extraer su información, sugerir la
        clasificación contable de cada ítem conforme al Plan Único de Cuentas y generar archivos
        de exportación para su importación en sistemas contables, actualmente SIIGO.
      </P>

      <Callout titulo="Lo que Ciolix NO es">
        <UL>
          <li>
            <Term>No es una firma contable</Term> ni presta servicios de contaduría pública,
            revisoría fiscal, auditoría o asesoría tributaria.
          </li>
          <li>
            <Term>No emite conceptos ni asesoría</Term> en materia contable, tributaria o legal.
          </li>
          <li>
            <Term>No presenta declaraciones ni interactúa con la DIAN</Term> en tu nombre. No
            solicitamos ni almacenamos tus credenciales de la DIAN.
          </li>
          <li>
            <Term>No sustituye el juicio profesional</Term> del contador público responsable de la
            información financiera.
          </li>
        </UL>
      </Callout>

      <P>
        La Compañía no es contribuyente ni responsable de las obligaciones tributarias del
        Cliente, ni responde por sanciones, intereses de mora, rechazos de costos o deducciones, o
        cualquier consecuencia derivada de la información que el Cliente presente ante la DIAN o
        ante cualquier autoridad.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="ia" num={N["ia"]}>
        Inteligencia artificial y responsabilidad profesional
      </H2>
      <P>
        La Plataforma utiliza modelos de inteligencia artificial para sugerir cuentas contables y
        códigos de impuesto. El Cliente reconoce y acepta expresamente lo siguiente:
      </P>
      <OL>
        <li>
          Las salidas del modelo son <Term>sugerencias de carácter estadístico</Term>, no
          determinaciones contables. Pueden ser incorrectas, incompletas o inconsistentes.
        </li>
        <li>
          <Term>Ninguna causación se completa de forma automática.</Term> El sistema exige que una
          persona revise y confirme expresamente cada clasificación antes de generar el archivo de
          exportación.
        </li>
        <li>
          La <Term>revisión, validación y aprobación</Term> de cada clasificación es
          responsabilidad exclusiva del Cliente y del contador público que suscriba la información
          financiera.
        </li>
        <li>
          La Compañía <Term>no garantiza</Term> un porcentaje determinado de acierto en las
          sugerencias, ni que estas se ajusten a la política contable particular del Cliente.
        </li>
        <li>
          Al confirmar una sugerencia, el Cliente asume plenamente el registro contable resultante
          como propio.
        </li>
        <li>
          Las sugerencias <Term>pueden variar con el tiempo</Term> para una misma entrada, por la
          evolución de los modelos del proveedor, por cambios en el catálogo del Cliente o por el
          histórico de decisiones acumulado. Esa variabilidad es propia de la tecnología y no
          constituye incumplimiento ni defecto del servicio.
        </li>
      </OL>
      <P>
        El detalle de qué información se envía al modelo, qué no se envía y cómo se protege está
        en la sección {NP["ia"]} de la{" "}
        <Link href="/legal/privacidad" style={{ color: "var(--brand)" }}>
          Política de Privacidad
        </Link>
        .
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="cuenta" num={N["cuenta"]}>
        Cuenta, credenciales y acceso
      </H2>
      <P>
        Para usar la Plataforma debes crear una cuenta con tu nombre, correo electrónico, una
        contraseña y los datos de tu empresa. Las credenciales son personales e intransferibles.
      </P>
      <UL>
        <li>
          Eres responsable de toda actividad realizada desde tu cuenta, incluso si la ejecuta un
          tercero que accedió a tus credenciales.
        </li>
        <li>
          Debes notificarnos de inmediato a {ENTIDAD.emailSoporte} cualquier uso no autorizado o
          sospecha de compromiso de tu cuenta.
        </li>
        <li>
          En los planes que permiten varios usuarios, el titular del plan es responsable de las
          cuentas que cree y del uso que hagan de ellas.
        </li>
        <li>
          La sesión se cierra automáticamente tras diez (10) minutos de inactividad, por seguridad.
        </li>
      </UL>

      <H3>Acceso programático e integraciones</H3>
      <P>
        El acceso a la Plataforma está previsto a través de su interfaz web. Cualquier acceso
        automatizado —scripts, robots, scraping o integraciones contra sus servicios internos— sin
        autorización escrita de la Compañía está prohibido y podrá dar lugar a la suspensión
        inmediata de la cuenta.
      </P>
      <P>
        Si la Compañía habilita una API pública, su uso se regirá por estos términos y por las
        condiciones técnicas que se publiquen junto con ella, que podrán incluir credenciales
        propias, límites de frecuencia y de volumen, y la facultad de restringir o suspender el
        acceso ante un uso que degrade el servicio para otros clientes. La Compañía podrá aplicar
        límites técnicos razonables para preservar la estabilidad de la Plataforma, informándolo
        previamente cuando ello afecte el uso normal del Plan contratado.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="planes" num={N["planes"]}>
        Planes, límites y tarifas
      </H2>
      <P>
        El alcance del servicio lo determina el Plan contratado. Cada Plan establece límites sobre:
      </P>
      <UL>
        <li>el número de usuarios que pueden acceder;</li>
        <li>el número de empresas que se pueden administrar;</li>
        <li>el número de causaciones procesables por ciclo mensual.</li>
      </UL>
      <P>
        Los Planes vigentes, sus límites y sus Tarifas se publican en{" "}
        <Term>{ENTIDAD.urlPlanes}</Term>. La versión publicada allí al momento de la contratación
        o de la renovación es la que prevalece. Las Tarifas se expresan en pesos colombianos y no
        incluyen el IVA ni otros impuestos aplicables, que se liquidarán de acuerdo con la
        normativa vigente.
      </P>
      <P>
        Al alcanzar el límite de causaciones de tu ciclo, la Plataforma te lo informará y podrás
        continuar mejorando de Plan. La Compañía no generará cobros adicionales por excedentes sin
        tu autorización previa y expresa.
      </P>
      <P>
        La Compañía puede modificar sus Tarifas. Los cambios se comunicarán con al menos treinta
        (30) días calendario de antelación y solo aplicarán a partir del ciclo siguiente. Si no
        estás de acuerdo, puedes cancelar antes de la renovación conforme a la sección {N["vigencia"]}, sin
        penalidad.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="pago" num={N["pago"]}>
        Pago, facturación y mora
      </H2>
      <UL>
        <li>La Tarifa se paga por anticipado al inicio de cada ciclo de facturación.</li>
        <li>
          La Compañía expedirá la factura electrónica correspondiente conforme a la normativa de la
          DIAN y la remitirá al correo de facturación que registres.
        </li>
        <li>
          Si un pago no se realiza en la fecha pactada, la Compañía podrá suspender el acceso tras
          notificarte y otorgarte un plazo de subsanación de cinco (5) días hábiles.
        </li>
        <li>
          Durante la suspensión por mora conservaremos tu Contenido del Cliente por treinta (30)
          días. Transcurrido ese plazo sin regularizar el pago, la cuenta podrá darse por terminada
          y los datos eliminarse conforme a la Política de Privacidad.
        </li>
        <li>
          Las sumas en mora podrán causar intereses moratorios a la máxima tasa legalmente
          permitida.
        </li>
      </UL>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="vigencia" num={N["vigencia"]}>
        Vigencia, renovación y cancelación
      </H2>
      <P>
        La suscripción se contrata por el período del Plan elegido y se renueva automáticamente
        por períodos iguales, salvo cancelación.
      </P>

      <H3>Cancelación</H3>
      <P>
        <Term>Puedes cancelar en cualquier momento, sin preaviso ni penalidad</Term>, desde tu
        cuenta o escribiendo a {ENTIDAD.emailSoporte}. La cancelación surte efecto al final del
        ciclo de facturación en curso: conservarás el acceso completo hasta esa fecha y no se
        generarán cobros posteriores.
      </P>
      <P>
        Salvo el caso previsto en la sección {N["retracto"]}, la cancelación a mitad de ciclo no da lugar a
        reembolso proporcional del período ya pagado, precisamente porque el acceso se mantiene
        hasta que ese período termina.
      </P>

      <H3>Exportación de tus datos</H3>
      <P>
        A partir de la fecha efectiva de cancelación dispones de <Term>treinta (30) días</Term>{" "}
        para exportar tu Contenido del Cliente. Vencido ese plazo, procederemos a su eliminación
        conforme a la Política de Privacidad.
      </P>

      <H3>Terminación por parte de la Compañía</H3>
      <P>
        La Compañía puede terminar el contrato con treinta (30) días de preaviso si decide
        descontinuar el servicio, en cuyo caso reembolsará la parte proporcional no consumida del
        período pagado. También puede terminarlo de inmediato en los casos previstos en la sección{" "}
        {N["suspension"]}.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="retracto" num={N["retracto"]}>
        Derecho de retracto y garantía del primer mes
      </H2>
      <P>
        Cuando el Cliente tenga la condición de consumidor en los términos de la Ley 1480 de 2011
        y la contratación se haya realizado por medios electrónicos, podrá ejercer el{" "}
        <Term>derecho de retracto</Term> dentro de los cinco (5) días hábiles siguientes a la
        celebración del contrato, con las excepciones que la misma ley contempla, entre ellas la
        de los servicios cuya prestación ya inició con el acuerdo del consumidor.
      </P>
      <Callout titulo="Garantía comercial de satisfacción">
        Con independencia de si el retracto legal resulta aplicable, la Compañía ofrece a todo
        Cliente nuevo la posibilidad de cancelar dentro de los primeros <Term>treinta (30) días</Term>{" "}
        de su primera suscripción y obtener el <Term>reembolso íntegro</Term> de lo pagado por ese
        primer período. Basta con solicitarlo a {ENTIDAD.emailSoporte}. El reembolso se realizará
        por el mismo medio de pago dentro de los quince (15) días hábiles siguientes.
      </Callout>
      <P>
        Igualmente, cuando resulte aplicable, el Cliente podrá solicitar la reversión del pago en
        los supuestos y condiciones del artículo 51 de la Ley 1480 de 2011.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="datos-cliente" num={N["datos-cliente"]}>
        Propiedad de tus datos
      </H2>
      <UL>
        <li>
          <Term>El Contenido del Cliente es y sigue siendo del Cliente.</Term> La Compañía no
          adquiere ningún derecho de propiedad sobre las facturas, catálogos, causaciones ni demás
          información que cargues o generes.
        </li>
        <li>
          El Cliente otorga a la Compañía una licencia limitada, no exclusiva y revocable para
          alojar, procesar y transmitir el Contenido del Cliente{" "}
          <Term>con el único fin de prestar el servicio contratado</Term>, durante la vigencia de
          la suscripción.
        </li>
        <li>
          <Term>La Compañía no usa el Contenido del Cliente para entrenar modelos de inteligencia
          artificial</Term>, ni lo comercializa, ni lo comparte con otros clientes.
        </li>
        <li>
          El aprendizaje que la Plataforma genera a partir de las decisiones del Cliente se aplica
          exclusivamente dentro del ámbito de ese Cliente y de la empresa correspondiente.
        </li>
        <li>
          La Compañía puede elaborar estadísticas agregadas y anonimizadas sobre el uso de la
          Plataforma, siempre que de ellas no sea posible identificar a ningún Cliente, empresa ni
          persona.
        </li>
      </UL>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="propiedad" num={N["propiedad"]}>
        Propiedad intelectual y licencia de uso
      </H2>
      <P>
        La Plataforma, su código, diseño, marcas, documentación y todo elemento que la compone son
        propiedad exclusiva de la Compañía o de sus licenciantes, y están protegidos por las normas
        de propiedad intelectual aplicables.
      </P>
      <P>
        Durante la vigencia de la suscripción, la Compañía concede al Cliente una licencia de uso{" "}
        <Term>limitada, no exclusiva, no transferible, no sublicenciable y revocable</Term>, para
        acceder y usar la Plataforma en su operación interna. Cualquier derecho no concedido
        expresamente queda reservado.
      </P>

      <H3>Mejoras y modelos derivados del funcionamiento</H3>
      <P>
        Es necesario distinguir dos cosas que suelen confundirse:
      </P>
      <UL>
        <li>
          <Term>El aprendizaje de tu empresa es tuyo y es tuyo en exclusiva.</Term> El histórico de
          decisiones, los mapeos de cuentas y las correcciones que confirmas forman parte del
          Contenido del Cliente, se aplican únicamente dentro de tu ámbito y no se comparten con
          otros clientes ni se usan para entrenar modelos, según la sección {N["datos-cliente"]}.
        </li>
        <li>
          <Term>El software, las reglas y los algoritmos son de la Compañía.</Term> Los motores de
          clasificación, las reglas contables genéricas, los diccionarios del PUC, las heurísticas
          de ranking y cualquier mejora que la Compañía desarrolle a partir de la operación
          agregada de la Plataforma son y seguirán siendo propiedad intelectual de la Compañía,{" "}
          <Term>siempre que no incorporen datos identificables de ningún Cliente</Term>.
        </li>
      </UL>
      <P>
        Dicho de otro modo: si al operar la Plataforma la Compañía descubre que cierto tipo de
        gasto suele clasificarse de determinada manera, puede incorporar ese conocimiento genérico
        al producto. Lo que no puede hacer, y no hace, es trasladar los datos, los proveedores o
        el histórico de un Cliente al ámbito de otro.
      </P>
      <P>
        Las sugerencias de mejora, comentarios o reportes de error que el Cliente envíe
        voluntariamente podrán ser incorporados al producto sin que ello genere contraprestación
        ni derecho de coautoría, y sin que la Compañía adquiera derecho alguno sobre el Contenido
        del Cliente que los acompañe.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="obligaciones" num={N["obligaciones"]}>
        Obligaciones del Cliente
      </H2>
      <OL>
        <li>Pagar oportunamente la Tarifa del Plan contratado.</li>
        <li>Suministrar información veraz y mantenerla actualizada.</li>
        <li>Custodiar sus credenciales y notificar cualquier uso no autorizado.</li>
        <li>
          Revisar y validar toda clasificación contable antes de confirmarla y de incorporarla a
          su sistema contable.
        </li>
        <li>
          Contar con la autorización o el fundamento legal necesario para cargar datos personales
          de terceros, y cumplir sus obligaciones como responsable del tratamiento respecto de
          ellos.
        </li>
        <li>Usar la Plataforma conforme a la ley y a estos términos.</li>
        <li>Tratar con respeto al personal de soporte de la Compañía.</li>
      </OL>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="prohibiciones" num={N["prohibiciones"]}>
        Conductas prohibidas
      </H2>
      <P>El Cliente se abstendrá de:</P>
      <OL>
        <li>
          Ceder, revender, sublicenciar, arrendar o poner la Plataforma a disposición de terceros
          ajenos a su organización.
        </li>
        <li>
          Descompilar, desensamblar, aplicar ingeniería inversa o intentar obtener el código fuente
          de la Plataforma.
        </li>
        <li>
          Usar la Plataforma para construir un producto o servicio competidor, o para extraer
          masivamente su contenido.
        </li>
        <li>
          Vulnerar o intentar vulnerar los mecanismos de seguridad, acceder a datos de otros
          clientes o realizar pruebas de intrusión sin autorización escrita previa de la Compañía.
        </li>
        <li>Interferir con la disponibilidad o el rendimiento de la Plataforma.</li>
        <li>
          Cargar contenido ilícito, malicioso o datos personales obtenidos sin la autorización
          legalmente exigida.
        </li>
        <li>
          Usar técnicas dirigidas a eludir los límites del Plan o el pago de la Tarifa, incluido el
          registro de múltiples cuentas con ese propósito.
        </li>
        <li>
          Intentar manipular el comportamiento de los modelos de inteligencia artificial mediante
          instrucciones incrustadas en el contenido que se carga.
        </li>
      </OL>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="disponibilidad" num={N["disponibilidad"]}>
        Disponibilidad, soporte y mantenimiento
      </H2>
      <P>
        La Compañía hará sus esfuerzos comercialmente razonables para mantener la Plataforma
        disponible de forma continua, con un objetivo de disponibilidad mensual del{" "}
        <Term>99%</Term>, calculado sobre el mes calendario y excluyendo las ventanas de
        mantenimiento programado y los eventos de fuerza mayor.
      </P>
      <Tabla
        headers={["Concepto", "Compromiso"]}
        rows={[
          ["Objetivo de disponibilidad mensual", "99%, excluyendo mantenimiento programado y fuerza mayor"],
          ["Aviso de mantenimiento programado", "Al menos 24 horas de antelación, por correo electrónico"],
          ["Mantenimiento de emergencia", "Aviso tan pronto como sea posible; puede ejecutarse sin preaviso si la seguridad lo exige"],
          ["Canal de soporte", ENTIDAD.emailSoporte],
          ["Horario de atención", "Días hábiles en Colombia, de [horario]"],
          ["Primera respuesta a incidentes críticos", "8 horas hábiles"],
          ["Primera respuesta a solicitudes generales", "2 días hábiles"],
        ]}
      />
      <P>
        La Compañía podrá modificar, actualizar o descontinuar funcionalidades. Si una modificación
        reduce de forma sustancial y permanente el alcance del servicio contratado, se notificará
        con treinta (30) días de antelación y el Cliente podrá cancelar sin penalidad, con
        reembolso proporcional del período no consumido.
      </P>
      <P>
        Los tiempos de indisponibilidad atribuibles a fallas en los equipos, redes o sistemas del
        Cliente, o a servicios de terceros ajenos al control de la Compañía, no se computan para el
        cálculo de disponibilidad.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="continuidad" num={N["continuidad"]}>
        Continuidad, respaldos y fuerza mayor
      </H2>

      <H3>Dependencia de proveedores de infraestructura</H3>
      <P>
        La Plataforma se apoya en servicios de terceros para operar: alojamiento de la aplicación
        y de la base de datos, entrega de la interfaz web, el modelo de inteligencia artificial y
        el envío de correo. Una interrupción en cualquiera de ellos puede afectar total o
        parcialmente el servicio sin que la Compañía pueda evitarlo.
      </P>
      <P>
        Se consideran eventos de fuerza mayor o caso fortuito, además de los reconocidos por la
        ley colombiana, los siguientes cuando escapen al control razonable de la Compañía:
      </P>
      <UL>
        <li>caídas o degradación de los proveedores de nube donde se aloja la Plataforma;</li>
        <li>
          indisponibilidad, cambios unilaterales o suspensión del servicio del proveedor del
          modelo de inteligencia artificial;
        </li>
        <li>fallas del proveedor de entrega de la interfaz web o de resolución de dominios;</li>
        <li>interrupciones de los operadores de internet o del suministro eléctrico;</li>
        <li>
          ataques de denegación de servicio, ransomware u otros ataques informáticos dirigidos a
          la Compañía o a sus proveedores;
        </li>
        <li>
          cambios normativos o decisiones de autoridad que impidan seguir prestando el servicio en
          las condiciones pactadas.
        </li>
      </UL>
      <P>
        Ante uno de estos eventos, la Compañía informará al Cliente por correo electrónico y le
        indicará, en cuanto lo conozca, el tiempo estimado de restablecimiento. Estos períodos no
        se computan para el cálculo de disponibilidad de la sección {N["disponibilidad"]} ni
        generan responsabilidad para la Compañía. Si la indisponibilidad se prolonga por más de{" "}
        <Term>quince (15) días calendario continuos</Term>, el Cliente podrá terminar el contrato
        y solicitar el reembolso proporcional del período pagado y no disfrutado.
      </P>

      <H3>Respaldos y conservación de la información</H3>
      <P>
        La Compañía adopta medidas razonables para preservar la integridad de la información
        alojada, pero <Term>no ofrece un servicio de respaldo ni de archivo</Term> a favor del
        Cliente, y no garantiza la recuperación íntegra de los datos ante un evento
        extraordinario, un fallo de infraestructura o un ataque informático.
      </P>
      <Callout titulo="Conserva tus propias copias">
        La Plataforma permite exportar en cualquier momento las causaciones y los archivos
        generados. El Cliente es responsable de descargar y conservar sus propias copias, y de
        mantener en su sistema contable el registro definitivo de la información. El repositorio
        legal y contable de la empresa es su ERP, no {ENTIDAD.marca}.
      </Callout>
      <P>
        Si la Compañía llega a ofrecer respaldos con niveles de recuperación garantizados, lo hará
        mediante una condición específica del Plan y así se indicará expresamente en{" "}
        {ENTIDAD.urlPlanes}.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="garantias" num={N["garantias"]}>
        Garantías y limitación de responsabilidad
      </H2>
      <P>
        La Compañía garantiza que prestará el servicio de manera profesional y diligente, conforme
        a lo descrito en estos términos. Salvo por esa garantía y por las que resulten
        irrenunciables por ley, la Plataforma se provee <Term>en el estado en que se encuentra</Term>.
      </P>
      <P>La Compañía no será responsable, en ningún caso, por:</P>
      <OL>
        <li>
          Errores en la clasificación contable derivados de sugerencias que el Cliente confirmó sin
          revisar.
        </li>
        <li>
          Sanciones, intereses, mayores impuestos, rechazo de costos o deducciones, o cualquier
          consecuencia tributaria o contable de la información que el Cliente presente ante
          autoridades.
        </li>
        <li>Daños indirectos, lucro cesante, pérdida de oportunidad o daño reputacional.</li>
        <li>Fallas en equipos, redes o sistemas del Cliente, o en servicios de terceros.</li>
        <li>
          Uso no autorizado de la cuenta del Cliente derivado del incumplimiento de sus deberes de
          custodia de credenciales.
        </li>
        <li>
          Eventos de fuerza mayor o caso fortuito, incluidos los descritos en la sección{" "}
          {N["continuidad"]}.
        </li>
      </OL>
      <Callout titulo="Tope de responsabilidad">
        La responsabilidad total y acumulada de la Compañía frente al Cliente, por cualquier
        causa y bajo cualquier teoría jurídica, no excederá el monto efectivamente pagado por el
        Cliente en los <Term>doce (12) meses</Term> anteriores al hecho que originó la
        reclamación.
      </Callout>
      <P>
        Estas limitaciones no aplican en los casos de dolo o culpa grave de la Compañía, ni frente
        a responsabilidades que la ley colombiana declare irrenunciables, en particular las
        derivadas del Estatuto del Consumidor cuando el Cliente tenga esa condición.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="indemnidad" num={N["indemnidad"]}>
        Indemnidad
      </H2>
      <P>
        El Cliente mantendrá indemne a la Compañía frente a reclamaciones de terceros, incluidos
        los costos razonables de defensa, que se deriven de: (i) el incumplimiento de estos
        términos; (ii) el tratamiento de datos personales de terceros cargados sin la autorización
        o el fundamento legal necesario; (iii) el uso ilícito de la Plataforma; o (iv) la
        información que el Cliente presente ante autoridades a partir de los archivos generados.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="confidencialidad" num={N["confidencialidad"]}>
        Confidencialidad
      </H2>
      <P>
        Cada parte se obliga a mantener confidencial la información que reciba de la otra con
        ocasión de este contrato, a no divulgarla a terceros sin autorización escrita y a usarla
        únicamente para los fines aquí previstos. El Contenido del Cliente se considera información
        confidencial del Cliente. Esta obligación subsiste por cinco (5) años después de terminado
        el contrato y no cubre la información que sea de dominio público, la que la parte receptora
        ya conocía legítimamente, o aquella cuya revelación exija una autoridad competente.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="suspension" num={N["suspension"]}>
        Suspensión y terminación
      </H2>
      <P>La Compañía podrá suspender o terminar el acceso de forma inmediata cuando el Cliente:</P>
      <UL>
        <li>incurra en alguna de las conductas prohibidas de la sección {N["prohibiciones"]};</li>
        <li>incumpla el pago de la Tarifa en los términos de la sección {N["pago"]};</li>
        <li>
          use la Plataforma de forma que comprometa su seguridad, su operación o los datos de otros
          clientes;
        </li>
        <li>suministre información falsa o suplante la identidad de un tercero.</li>
      </UL>
      <P>
        Salvo que la gravedad o la urgencia lo impidan, la Compañía notificará previamente al
        Cliente y le otorgará un plazo razonable para subsanar. Terminado el contrato, cesa la
        licencia de uso y aplican los plazos de exportación y eliminación de datos previstos en la
        sección {N["vigencia"]}.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="datos-personales" num={N["datos-personales"]}>
        Tratamiento de datos personales
      </H2>
      <P>
        El tratamiento de datos personales se rige por la{" "}
        <Link href="/legal/privacidad" style={{ color: "var(--brand)" }}>
          Política de Privacidad y Tratamiento de Datos Personales
        </Link>
        , que forma parte integral de este contrato.
      </P>
      <P>
        Las partes reconocen expresamente que, respecto de los datos personales de terceros
        contenidos en las facturas y catálogos que el Cliente carga,{" "}
        <Term>el Cliente actúa como responsable del tratamiento y la Compañía como encargado</Term>
        . En esa condición, la Compañía tratará dichos datos únicamente siguiendo las instrucciones
        del Cliente y con el fin de prestar el servicio, guardará confidencialidad sobre ellos,
        adoptará las medidas de seguridad descritas en la Política de Privacidad y los devolverá o
        suprimirá al terminar el contrato, conforme a los plazos allí previstos.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="pqrs" num={N["pqrs"]}>
        Peticiones, quejas, reclamos y sugerencias
      </H2>
      <P>
        Las PQRS se reciben en <Term>{ENTIDAD.emailSoporte}</Term> y en el teléfono{" "}
        {ENTIDAD.telefono}. Cada solicitud se radica con un número de caso que se comunica a quien
        la presenta. La Compañía responderá dentro de los <Term>quince (15) días hábiles</Term>{" "}
        siguientes a su recepción.
      </P>
      <P>
        Las solicitudes relativas al ejercicio de derechos sobre datos personales se tramitan por
        el canal y en los plazos indicados en la sección {NP["derechos"]} de la Política de Privacidad.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="modificaciones" num={N["modificaciones"]}>
        Modificaciones
      </H2>
      <P>
        La Compañía puede modificar estos términos. Cada versión lleva número y fecha de vigencia
        visibles al inicio del documento. Los cambios sustanciales se notificarán por correo
        electrónico con al menos <Term>quince (15) días calendario</Term> de antelación a su
        entrada en vigor.
      </P>
      <P>
        Si no estás de acuerdo con la nueva versión, puedes cancelar antes de que entre en vigor
        sin penalidad alguna. El uso de la Plataforma después de esa fecha implica su aceptación.
        Los cambios no tienen efecto retroactivo.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="ley" num={N["ley"]}>
        Ley aplicable y resolución de conflictos
      </H2>
      <P>
        Este contrato se rige por las leyes de la República de Colombia.
      </P>
      <P>
        Ante cualquier controversia, las partes intentarán de buena fe un arreglo directo durante
        un plazo de <Term>treinta (30) días calendario</Term> contados desde la comunicación
        escrita del reclamo. Si no se llega a un acuerdo, la controversia se someterá a los jueces
        competentes de la República de Colombia.
      </P>
      <P>
        Cuando el Cliente tenga la condición de consumidor, conserva íntegramente el derecho a
        acudir ante la Superintendencia de Industria y Comercio en ejercicio de las acciones
        previstas en la Ley 1480 de 2011, sin que las etapas previas aquí pactadas constituyan un
        obstáculo para ello.
      </P>

      {/* ─────────────────────────────────────────────────────────────── */}
      <H2 id="varios" num={N["varios"]}>
        Disposiciones varias
      </H2>
      <UL>
        <li>
          <Term>Acuerdo íntegro:</Term> estos términos y la Política de Privacidad constituyen el
          acuerdo completo entre las partes sobre su objeto.
        </li>
        <li>
          <Term>Divisibilidad:</Term> si una cláusula se declara inválida, las demás conservan su
          plena vigencia.
        </li>
        <li>
          <Term>No renuncia:</Term> la tolerancia frente a un incumplimiento no implica renuncia a
          exigir su cumplimiento posterior.
        </li>
        <li>
          <Term>Cesión:</Term> el Cliente no puede ceder este contrato sin autorización escrita de
          la Compañía. La Compañía puede cederlo en el marco de una reorganización empresarial,
          notificándolo al Cliente con treinta (30) días de antelación.
        </li>
        <li>
          <Term>Independencia:</Term> nada en este contrato crea una relación laboral, de
          sociedad, de agencia o de mandato entre las partes.
        </li>
        <li>
          <Term>Notificaciones:</Term> se harán al correo electrónico registrado por el Cliente y
          a {ENTIDAD.emailSoporte} en el caso de la Compañía.
        </li>
      </UL>

      <div
        className="mt-14 border-t pt-6 text-sm"
        style={{ borderColor: "var(--border-soft)", color: "var(--text-muted)" }}
      >
        Consulta también nuestra{" "}
        <Link href="/legal/privacidad" style={{ color: "var(--brand)" }}>
          Política de Privacidad
        </Link>
        .
      </div>
    </Documento>
  );
}
