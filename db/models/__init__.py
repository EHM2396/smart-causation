"""
Punto de entrada único para importar modelos.
Importar Base aquí asegura que todos los modelos queden registrados
en el metadata de SQLAlchemy antes de llamar a Base.metadata.create_all().
"""

from db.base import Base                                   # noqa: F401
from db.models.auth import (                               # noqa: F401
    Plan,
    Usuario,
    Empresa,
    UsuarioEmpresa,
)
from db.models.legal import (                              # noqa: F401
    Consentimiento,
)
from db.models.catalogo import (                           # noqa: F401
    CuentaContable,
    CodigoImpuesto,
    TipoComprobante,
)
from db.models.contabilidad import (                       # noqa: F401
    Proveedor,
    FacturaCausada,
    Consecutivo,
)
from db.models.aprendizaje import (                        # noqa: F401
    MapeoPUC,
    HistorialDecision,
    ReglaClasificacion,
)
from db.models.geo import (                                # noqa: F401
    TipoIdentificacion,
    Pais,
    Departamento,
    Ciudad,
    SiigoTipoPersona,
    SiigoRegimenIva,
    SiigoResponsabilidadFiscal,
)

__all__ = [
    "Base",
    "Plan",
    "Usuario",
    "Empresa",
    "UsuarioEmpresa",
    "Consentimiento",
    "CuentaContable",
    "CodigoImpuesto",
    "TipoComprobante",
    "Proveedor",
    "FacturaCausada",
    "Consecutivo",
    "MapeoPUC",
    "HistorialDecision",
    "ReglaClasificacion",
    "TipoIdentificacion",
    "Pais",
    "Departamento",
    "Ciudad",
    "SiigoTipoPersona",
    "SiigoRegimenIva",
    "SiigoResponsabilidadFiscal",
]
