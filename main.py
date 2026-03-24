from reportlab.lib.styles import getSampleStyleSheet
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Bot activo"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    Thread(target=run).start()

import discord
from discord.ext import commands
import os
import json
from datetime import datetime

# ---------------- CONFIG ----------------
TOKEN = os.environ.get("DISCORD_TOKEN")

OWNER_ID = 583251995729723393
SECOND_USER_ID = 1085972230644711455  # ← pon aquí el ID de la otra persona

QUEUE_CHANNEL_ID = 1485632967866056745
LOG_COMANDOS_ID = 1485699759736885318
LOG_CHANNEL_ID = 1485937001038479451
LOG_BORRADOS_ID = 1485706506207756499
REGISTROS_CHANNEL_ID = 1485829389357944982

DATA_FILE = "data.json"
QUEUE_FILE = "cola.txt"
QUEUE_MESSAGE_ID_FILE = "queue_msg_id.txt"
REGISTROS_MESSAGE_ID_FILE = "registros_msg_id.txt"

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")

@bot.event
async def on_command(ctx):
    try:
        log_channel = await bot.fetch_channel(LOG_COMANDOS_ID)

        embed = discord.Embed(
            title="📌 Comando usado",
            color=discord.Color.purple()
        )

        embed.add_field(name="Usuario", value=ctx.author.mention)
        embed.add_field(name="Comando", value=ctx.message.content)
        embed.add_field(name="Canal", value=ctx.channel.mention)

        await log_channel.send(embed=embed)

    except Exception as e:
        print("Error log comandos:", e)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ No tienes permiso para usar este comando")

# ---------------- FUNCIONES ----------------
def es_owner(ctx):
    return ctx.author.id in [OWNER_ID, SECOND_USER_ID]

def cargar_datos():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_datos(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def leer_cola():
    if not os.path.exists(QUEUE_FILE):
        return []
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        return f.readlines()

def guardar_cola(lineas):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        f.writelines(lineas)

# ---------------- COLA ----------------
async def actualizar_mensaje_cola():
    channel = bot.get_channel(QUEUE_CHANNEL_ID)

    if channel is None:
        print("❌ Canal de cola no encontrado")
        return

    cola = leer_cola()
    texto = "\n".join([f"🔹 **{i+1}.** {line.strip()}" for i, line in enumerate(cola)]) or "Sin pedidos"

    embed = discord.Embed(
        title="📋 Cola de pedidos",
        description=texto,
        color=discord.Color.orange()
    )

    try:
        if os.path.exists(QUEUE_MESSAGE_ID_FILE):
            with open(QUEUE_MESSAGE_ID_FILE, "r") as f:
                msg_id = int(f.read())

            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed)
            return
    except:
        pass

    msg = await channel.send(embed=embed)

    with open(QUEUE_MESSAGE_ID_FILE, "w") as f:
        f.write(str(msg.id))

# ---------------- REGISTROS AVANZADOS (FIX PRO) ----------------
def agrupar_datos():
    data = cargar_datos()
    usuarios = {}

    for d in data:
        uid = d["id"]
        if uid not in usuarios:
            usuarios[uid] = {
                "usuario": d["usuario"],
                "id": uid,
                "pedidos": []
            }
        usuarios[uid]["pedidos"].append(d)

    return list(usuarios.values())


class RegistrosView(discord.ui.View):
    def __init__(self, usuarios, page=0):
        super().__init__(timeout=None)
        self.usuarios = usuarios
        self.page = page
        self.per_page = 10

    def get_embed(self):
        total_pages = max(1, (len(self.usuarios) - 1) // self.per_page + 1)

        start = self.page * self.per_page
        end = start + self.per_page
        usuarios_pagina = self.usuarios[start:end]

        descripcion = ""

        for u in usuarios_pagina:
            descripcion += f"**👤 NOMBRE: {u['usuario']} | ID: {u['id']}**\n"

            for p in u["pedidos"]:
                estado = p.get("estado", "sinestado")
                descripcion += f"↳ 📦 {p['producto']} | 💰 {p['precio']}€ | 📊 {estado.upper()}\n"

            descripcion += "\n"

        embed = discord.Embed(
            title="📊 REGISTROS DE CLIENTES",
            description=descripcion or "Sin datos",
            color=discord.Color.blue()
        )

        embed.set_footer(text=f"Página {self.page+1}/{total_pages}")

        return embed, total_pages

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page == 0:
            return await interaction.response.send_message("⚠️ Primera página", ephemeral=True)

        self.page -= 1
        embed, _ = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def siguiente(self, interaction: discord.Interaction, button: discord.ui.Button):
        _, total_pages = self.get_embed()

        if self.page >= total_pages - 1:
            return await interaction.response.send_message("⚠️ Última página", ephemeral=True)

        self.page += 1
        embed, _ = self.get_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="🔍", style=discord.ButtonStyle.primary)
    async def buscar(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("🔎 Escribe la ID:", ephemeral=True)

        def check(m):
            return m.author == interaction.user

        try:
            msg = await bot.wait_for("message", check=check, timeout=20)
        except:
            return await interaction.followup.send("⏰ Tiempo agotado", ephemeral=True)

        user_id = msg.content.strip()

        resultados = [u for u in self.usuarios if u["id"] == user_id]

        if not resultados:
            return await interaction.followup.send("❌ No encontrado", ephemeral=True)

        u = resultados[0]

        descripcion = f"**👤 {u['usuario']} | ID: {u['id']}**\n\n"

        for p in u["pedidos"]:
            estado = p.get("estado", "sinestado")
            descripcion += f"📦 {p['producto']} | 💰 {p['precio']}€ | 📊 {estado.upper()}\n"

        embed = discord.Embed(
            title="🔎 Resultado",
            description=descripcion,
            color=discord.Color.green()
        )

        await interaction.followup.send(embed=embed, ephemeral=True)


async def actualizar_registros():
    channel = bot.get_channel(REGISTROS_CHANNEL_ID)

    if channel is None:
        print("❌ Canal registros no encontrado")
        return

    usuarios = agrupar_datos()

    view = RegistrosView(usuarios)
    embed, _ = view.get_embed()

    try:
        if os.path.exists(REGISTROS_MESSAGE_ID_FILE):
            with open(REGISTROS_MESSAGE_ID_FILE, "r") as f:
                msg_id = int(f.read())

            msg = await channel.fetch_message(msg_id)
            await msg.edit(embed=embed, view=view)
            return
    except:
        pass

    msg = await channel.send(embed=embed, view=view)

    with open(REGISTROS_MESSAGE_ID_FILE, "w") as f:
        f.write(str(msg.id))
        
# ---------------- COMANDOS ----------------
@bot.command()
async def setup(ctx):
    if not es_owner(ctx):
        return

    if os.path.exists(QUEUE_MESSAGE_ID_FILE):
        os.remove(QUEUE_MESSAGE_ID_FILE)

    await actualizar_mensaje_cola()
    await ctx.send("✅ Cola configurada", delete_after=5)

@bot.command()
async def setup_registros(ctx):
    if not es_owner(ctx):
        return

    if os.path.exists(REGISTROS_MESSAGE_ID_FILE):
        os.remove(REGISTROS_MESSAGE_ID_FILE)

    await actualizar_registros()
    await ctx.send("✅ Panel registros creado", delete_after=5)

@bot.command()
async def añadir_cola(ctx, user: discord.Member, *, producto: str):
    if not es_owner(ctx):
        return

    await ctx.message.delete()

    # 🔥 ANTI DUPLICADOS (AQUÍ VA)
    cola = leer_cola()
    for linea in cola:
        if str(user.id) in linea:
            return await ctx.send("❌ Este usuario ya está en la cola", delete_after=5)

    linea = f"{user.name} | ID: {user.id} | Producto: {producto}\n"

    with open(QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(linea)

    cola = leer_cola()
    posicion = len(cola)

    await actualizar_mensaje_cola()

    embed = discord.Embed(
        title="✅ Añadido a la cola",
        description=f"{user.mention} está en el puesto #{posicion}",
        color=discord.Color.green()
    )

    await ctx.send(embed=embed, delete_after=5)

@bot.command()
async def siguiente(ctx):
    if not es_owner(ctx):
        return

    cola = leer_cola()
    if not cola:
        return await ctx.send("❌ Cola vacía")

    terminado = cola.pop(0)
    guardar_cola(cola)

    await actualizar_mensaje_cola()

    try:
        user_id = int(terminado.split("ID: ")[1].split(" | ")[0])
        user = await bot.fetch_user(user_id)

        embed = discord.Embed(
            title="✅ Pedido completado",
            description="Tu pedido ha sido terminado.\nDeja una reseña aquí 👉 <#1482528663650959370>",
            color=discord.Color.green()
        )

        await user.send(embed=embed)

    except Exception as e:
        print("Error MD usuario:", e)

    if cola:
        try:
            next_id = int(cola[0].split("ID: ")[1].split(" | ")[0])
            next_user = await bot.fetch_user(next_id)

            embed = discord.Embed(
                title="📩 Te toca pronto",
                description="Estate atento 👀",
                color=discord.Color.orange()
            )

            await next_user.send(embed=embed)

        except Exception as e:
            print("Error MD siguiente:", e)

@bot.command()
async def registrar(ctx, usuario: str, user_id: str, precio: str, *, producto: str):
    if not es_owner(ctx):
        return await ctx.send("❌ No tienes permiso")

    try:
        precio_val = float(precio.replace("€", "").replace(",", "."))
    except:
        return await ctx.send("❌ Precio inválido")

    # -------- GUARDAR --------
    data = cargar_datos()
    data.append({
        "usuario": usuario,
        "id": user_id,
        "producto": producto,
        "precio": precio_val,
        "fecha": datetime.now().strftime("%d/%m/%Y")
    })
    guardar_datos(data)

    await actualizar_registros()

    # -------- EMBED --------
    embed = discord.Embed(
        title="💰 Nueva compra",
        color=discord.Color.green()
    )
    embed.add_field(name="Usuario", value=usuario)
    embed.add_field(name="ID", value=user_id)
    embed.add_field(name="Producto", value=producto)
    embed.add_field(name="Precio", value=f"{precio_val}€")

    await ctx.send(embed=embed)

    # -------- LOG --------
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(embed=embed)

    # -------- FACTURA + MD --------
    try:
        user = await bot.fetch_user(int(user_id))

        factura_nombre = f"factura_{user_id}.txt"

        with open(factura_nombre, "w", encoding="utf-8") as f:
            f.write(
                f"Factura\n\n"
                f"Usuario: {usuario}\n"
                f"ID: {user_id}\n"
                f"Producto: {producto}\n"
                f"Precio: {precio_val}€"
            )

        await user.send(
            content="📄 Aquí tienes tu factura:",
            file=discord.File(factura_nombre)
        )

        os.remove(factura_nombre)

    except Exception as e:
        print("Error enviando factura:", e)
        
    # 🔥 ACTUALIZAR PANEL REGISTROS
    await actualizar_registros()

@bot.command()
async def cliente(ctx, user: discord.Member):
    if not es_owner(ctx):
        return

    data = cargar_datos()
    user_data = [d for d in data if d["id"] == str(user.id)]

    if not user_data:
        return await ctx.send("❌ Este usuario no tiene registros")

    total = sum(d["precio"] for d in user_data)

    embed = discord.Embed(
        title=f"📊 Cliente: {user.name}",
        color=discord.Color.blue()
    )

    embed.add_field(name="💰 Total gastado", value=f"{total}€", inline=False)
    embed.add_field(name="📦 Pedidos", value=len(user_data), inline=False)

    texto = ""
    for d in user_data:
        estado = d.get("estado", "desconocido")
        texto += f"{d['producto']} | {d['precio']}€ | {estado}\n"

    embed.description = texto[:4000]

    await ctx.send(embed=embed)
    
@bot.command()
async def stats(ctx):
    if not es_owner(ctx):
        return

    data = cargar_datos()

    if not data:
        return await ctx.send("❌ No hay datos")

    total_pedidos = len(data)
    total_dinero = sum(d["precio"] for d in data)

    embed = discord.Embed(
        title="📊 Estadísticas",
        color=discord.Color.blue()
    )

    embed.add_field(name="📦 Pedidos", value=total_pedidos, inline=False)
    embed.add_field(name="💰 Dinero generado", value=f"{total_dinero}€", inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def mover(ctx, user: discord.Member, posicion: int):
    if not es_owner(ctx):
        return

    cola = leer_cola()

    index = None
    for i, linea in enumerate(cola):
        if str(user.id) in linea:
            index = i
            break

    if index is None:
        return await ctx.send("❌ Usuario no está en la cola")

    usuario = cola.pop(index)

    if posicion < 1:
        posicion = 1
    if posicion > len(cola) + 1:
        posicion = len(cola) + 1

    cola.insert(posicion - 1, usuario)

    guardar_cola(cola)
    await actualizar_mensaje_cola()

    await ctx.send(f"🔄 {user.mention} movido a la posición #{posicion}")

@bot.command()
async def borrar_registro(ctx, user_id: str, *, filtro: str):
    if not es_owner(ctx):
        return

    await ctx.send("⚠️ Escribe **confirmar** para continuar")

    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    try:
        msg = await bot.wait_for("message", check=check, timeout=20)

        if msg.content.lower() != "confirmar":
            return await ctx.send("❌ Cancelado")

    except:
        return await ctx.send("⏰ Tiempo agotado")

    data = cargar_datos()
    nuevos = []
    eliminados = []

    for d in data:
        if d["id"] == user_id:
            if filtro.lower() == "todos" or filtro.lower() in d["producto"].lower():
                eliminados.append(d)
                continue

        nuevos.append(d)

    guardar_datos(nuevos)

    if eliminados:
        # 🔥 EMBED
        embed = discord.Embed(
            title="🗑️ Registros eliminados",
            color=discord.Color.red()
        )

        texto = ""
        for e in eliminados:
            texto += f"👤 {e['usuario']} | 📦 {e['producto']} | 💰 {e['precio']}€\n"

        embed.description = texto[:4000]

        await ctx.send(embed=embed)

        # 🔥 LOG
        try:
            log_channel = await bot.fetch_channel(LOG_BORRADOS_ID)
            await log_channel.send(embed=embed)
        except Exception as e:
            print("Error log borrado:", e)

    else:
        await ctx.send("❌ No se encontró ningún registro")

    # 🔥 ACTUALIZAR PANEL
    await actualizar_registros()

@bot.command()
async def borrar_cola(ctx, posicion: int):
    if not es_owner(ctx):
        return

    cola = leer_cola()

    if posicion < 1 or posicion > len(cola):
        return await ctx.send("❌ Posición inválida")

    eliminado = cola.pop(posicion - 1)
    guardar_cola(cola)

    await actualizar_mensaje_cola()

    embed = discord.Embed(
        title="🗑️ Pedido eliminado",
        description=f"Eliminado:\n{eliminado}",
        color=discord.Color.red()
    )

    await ctx.send(embed=embed, delete_after=5)

@bot.command()
async def mis_pedidos(ctx):
    data = cargar_datos()

    user_id = str(ctx.author.id)
    pedidos = [d for d in data if d["id"] == user_id]

    if not pedidos:
        return await ctx.send("❌ No tienes pedidos registrados")

    embed = discord.Embed(
        title="📦 Tus pedidos",
        color=discord.Color.blue()
    )

    texto = ""
    for p in pedidos:
        texto += f"📦 {p['producto']} | 💰 {p['precio']}€ | 📅 {p['fecha']}\n"

    embed.description = texto[:4000]

    await ctx.send(embed=embed)

# ---------------- START ----------------
if not TOKEN:
    print("❌ ERROR: No hay DISCORD_TOKEN")
    exit()

keep_alive()
bot.run(TOKEN)
