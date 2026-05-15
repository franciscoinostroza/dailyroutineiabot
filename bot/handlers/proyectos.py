from telegram.ext import ContextTypes

from bot.services.ai import openai_client
from bot.tools.proyectos import WorksheetProyectos, WorksheetDocumentacion


async def proyecto(update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text(
            "📁 USO: /proyecto <accion>\n\n"
            "Acciones:\n"
            "/proyecto listar — Ver todos los proyectos\n"
            "/proyecto crear <nombre> <descripcion> — Crear proyecto\n"
            "/proyecto ver <nombre> — Ver proyecto\n"
            "/proyecto readme <nombre> — Generar README.md\n"
            "/proyecto deploy <nombre> [detalle] — Generar guia de deploy\n"
            "/proyecto api <nombre> [rutas] — Generar doc de API\n"
            "/proyecto changelog <nombre> <cambio> — Agregar al changelog\n"
            "/proyecto cliente <nombre> — Doc para entregar al cliente\n"
            "/proyecto docs <nombre> — Listar docs generados\n"
            "/proyecto editar <nombre> <campo> <valor> — Editar campo del proyecto"
        )
        return

    sub = context.args[0].lower()

    if sub == "listar":
        proyectos = WorksheetProyectos.read_all()
        if not proyectos:
            await update.message.reply_text("No hay proyectos. Crea uno con /proyecto crear <nombre> <descripcion>")
            return
        msg = "📁 Proyectos:\n\n"
        for p in proyectos:
            estado = p.get("estado", "?")
            emoji = "🟢" if estado == "activo" else "🟡" if estado == "pausado" else "⚪"
            msg += f"{emoji} {p['nombre']} — {p.get('descripcion','')}\n"
        await update.message.reply_text(msg)

    elif sub == "crear":
        if len(context.args) < 3:
            await update.message.reply_text(
                "Uso: /proyecto crear <nombre> <descripcion>\n"
                "Ejemplo: /proyecto crear \"Web Cliente X\" \"Landing page + panel admin con React y Django\""
            )
            return
        nombre = context.args[1]
        descripcion = " ".join(context.args[2:])
        WorksheetProyectos.upsert(nombre, descripcion, estado="activo")
        await update.message.reply_text(
            f"✅ Proyecto creado: {nombre}\n"
            "Podes generar documentacion con:\n"
            "/proyecto readme <nombre>\n"
            "/proyecto deploy <nombre>\n"
            "/proyecto api <nombre>\n"
        )

    elif sub in ("ver", "info"):
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /proyecto ver <nombre>")
            return
        nombre = context.args[1]
        _, p = WorksheetProyectos.find_by_nombre(nombre)
        if p is None:
            await update.message.reply_text(f"Proyecto '{nombre}' no encontrado.")
            return

        from bot.tools.trabajo import _calcular_horas
        from datetime import datetime
        import pytz
        tz2 = pytz.timezone(settings.timezone)
        horas, sesiones, por_proy = _calcular_horas()
        horas_proy = por_proy.get(nombre, 0) / 60

        docs = WorksheetDocumentacion.read_by_proyecto(nombre)
        tipos_doc = list(set(d.get("tipo", "") for d in docs))

        msg = (
            f"📁 {p['nombre']}\n"
            f"   {p.get('descripcion', '')}\n"
            f"   Stack: {p.get('stack', '-')}\n"
            f"   Cliente: {p.get('cliente', '-')}\n"
            f"   Repo: {p.get('repo_url', '-')}\n"
            f"   Inicio: {p.get('fecha_inicio', '-')}\n"
            f"   Estado: {p.get('estado', '-')}\n"
            f"   ⏱ Horas este mes: {horas_proy:.1f}h\n"
        )
        if tipos_doc:
            msg += f"   📄 Docs: {', '.join(tipos_doc)}"
        await update.message.reply_text(msg)

    elif sub in ("docs", "documentos"):
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /proyecto docs <nombre>")
            return
        nombre = context.args[1]
        docs = WorksheetDocumentacion.read_by_proyecto(nombre)
        if not docs:
            await update.message.reply_text(f"No hay documentacion para '{nombre}'.")
            return
        msg = f"📄 Documentacion de {nombre}:\n\n"
        for d in docs:
            msg += f"  📎 {d.get('tipo','')} — {d.get('fecha_actualizacion','')}\n"
        await update.message.reply_text(msg)

    elif sub == "readme":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /proyecto readme <nombre>")
            return
        nombre = context.args[1]
        await _generar_doc(update, nombre, "readme", _prompt_readme)

    elif sub == "deploy":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /proyecto deploy <nombre>")
            return
        nombre = context.args[1]
        extra = " ".join(context.args[2:]) if len(context.args) > 2 else ""
        await _generar_doc(update, nombre, "deploy", _prompt_deploy, extra=extra)

    elif sub == "api":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /proyecto api <nombre> [rutas]")
            return
        nombre = context.args[1]
        extra = " ".join(context.args[2:]) if len(context.args) > 2 else ""
        await _generar_doc(update, nombre, "api", _prompt_api, extra=extra)

    elif sub == "changelog":
        if len(context.args) < 3:
            await update.message.reply_text("Uso: /proyecto changelog <nombre> <cambio>")
            return
        nombre = context.args[1]
        entrada = " ".join(context.args[2:])
        WorksheetDocumentacion.append_changelog(nombre, entrada)
        await update.message.reply_text(f"✅ Changelog actualizado: {nombre}")

    elif sub == "cliente":
        if len(context.args) < 2:
            await update.message.reply_text("Uso: /proyecto cliente <nombre>")
            return
        nombre = context.args[1]
        await _generar_doc(update, nombre, "cliente", _prompt_cliente)

    elif sub == "editar":
        if len(context.args) < 4:
            await update.message.reply_text(
                "Uso: /proyecto editar <nombre> <campo> <valor>\n"
                "Campos: stack, repo, cliente, estado"
            )
            return
        nombre = context.args[1]
        campo = context.args[2].lower()
        valor = " ".join(context.args[3:])
        campos_map = {"stack": "C", "repo": "D", "cliente": "E", "estado": "G"}
        if campo not in campos_map:
            await update.message.reply_text(f"Campo invalido. Usa: {', '.join(campos_map.keys())}")
            return
        row_idx, _ = WorksheetProyectos.find_by_nombre(nombre)
        if row_idx is None:
            await update.message.reply_text(f"Proyecto '{nombre}' no encontrado.")
            return
        ws = WorksheetProyectos.get()
        ws.update(f"{campos_map[campo]}{row_idx}", valor)
        await update.message.reply_text(f"✅ {campo} actualizado para {nombre}")

    else:
        await update.message.reply_text(f"Subcomando '{sub}' no reconocido. Usa /proyecto sin args para ayuda.")


_prompt_readme = (
    "Genera un README.md profesional para este proyecto."
    " Inclui: titulo, descripcion, tecnologias, instalacion, uso, deploy, estructura del proyecto y variables de entorno necesarias."
    " Las variables de entorno deben listarse CON NOMBRE PERO SIN VALORES REALES, usa <COMPLETAR> como placeholder."
    " NUNCA incluyas tokens, claves, contraseñas ni secretos reales."
    " Responde en español, en formato Markdown."
)

_prompt_deploy = (
    "Genera una guia de deploy profesional para este proyecto."
    " Inclui: requisitos del servidor, variables de entorno necesarias (con nombres pero SIN valores, usa <COMPLETAR>),"
    " pasos de instalacion, comandos de deploy, y verificacion."
    " NUNCA incluyas tokens, claves, contraseñas ni secretos reales."
    " Responde en español, en formato Markdown."
)

_prompt_api = (
    "Genera documentacion de API para este proyecto."
    " Lista los endpoints con metodo HTTP, ruta, parametros, body de ejemplo y respuesta esperada."
    " Si no hay rutas especificas, inferi las tipicas del stack del proyecto."
    " NUNCA incluyas tokens, claves, contraseñas ni secretos reales."
    " Responde en español, en formato Markdown."
)

_prompt_cliente = (
    "Genera un documento para entregar al cliente final del proyecto."
    " Inclui: resumen de lo entregado, tecnologias usadas, como acceder, credenciales necesarias (usa <COMPLETAR>),"
    " pasos para cambiar contraseñas, y contacto."
    " El tono debe ser profesional y amigable."
    " NUNCA incluyas tokens, claves, contraseñas ni secretos reales."
    " Responde en español, en formato Markdown."
)


async def _generar_doc(update, context, nombre, prompt_fn, extra=""):
    _, p = WorksheetProyectos.find_by_nombre(nombre)
    if p is None:
        await update.message.reply_text(f"Proyecto '{nombre}' no encontrado. Creálo con /proyecto crear.")
        return

    await update.message.reply_text(f"Generando documentacion para {nombre}...")

    tipo = update.message.text.split()[1].lower()

    docs_existente = WorksheetDocumentacion.read_by_proyecto(nombre, tipo)
    existing_content = docs_existente[0].get("contenido", "") if docs_existente else ""

    context_text = (
        f"Proyecto: {p['nombre']}\n"
        f"Descripcion: {p.get('descripcion', '')}\n"
        f"Stack: {p.get('stack', '')}\n"
        f"Repo: {p.get('repo_url', '')}\n"
        f"Cliente: {p.get('cliente', '')}\n"
    )
    if extra:
        context_text += f"Informacion adicional del usuario: {extra}\n"
    if existing_content:
        context_text += f"\nDocumentacion existente (mejorala, no la reemplaces completamente):\n{existing_content}"

    user_prompt = f"{prompt_fn}\n\nInformacion del proyecto:\n{context_text}"

    try:
        from bot.config import settings
        response = await openai_client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=1500,
        )
        doc = response.choices[0].message.content or ""
    except Exception as e:
        await update.message.reply_text(f"Error generando documentacion: {e}")
        return

    WorksheetDocumentacion.upsert(nombre, tipo, doc)
    await update.message.reply_text(f"📄 {tipo} generado y guardado:\n\n{doc[:4000]}")
    if len(doc) > 4000:
        await update.message.reply_text(f"... (documento completo guardado en Google Sheets, usa /proyecto docs {nombre})")
