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

QUEUE_CHANNEL_ID = 1485632967866056745
LOG_CHANNEL_ID = 1485699759736885318
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

# ---------------- FUNCIONES ----------------
def es_owner(ctx):
    return ctx.author.id == OWNER_ID

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

# ---------------- REGISTROS AVANZADOS ----------------
def agrupar_datos():
    data = cargar_datos()
    agrupado = {}

    for d in data:
        if d["id"] not in agrupado:
            agrupado[d["id"]] = {
                "usuario": d["usuario"],
                "id": d["id"],
                "pedidos": []
            }
        agrupado[d["id"]]["pedidos"].append(d)

    return list(agrupado.values())

def generar_paginas():
    usuarios = agrupar_datos()
    paginas = []
    texto = ""

    for u in usuarios:
        bloque = f"**NOMBRE:** {u['usuario']} | ID: {u['id']}\n"

        for p in u["pedidos"]:
            bloque += f"nombre: {u['usuario']} | id: {u['id']} | producto: {p['producto']} | precio: {p['precio']}€\n"

        bloque += "\n"

        if len(texto) + len(bloque) > 3500:
            paginas.append(texto)
            texto = bloque
        else:
            texto += bloque

    if texto:
        paginas.append(texto)

    return paginas if paginas else ["No hay registros"]

class RegistrosView(discord.ui.View):
    def __init__(self, paginas):
        super().__init__(timeout=None)
        self.paginas = paginas
        self.index = 0

    async def update(self, interaction):
        embed = discord.Embed(
            title="📊 REGISTROS DE CLIENTES",
            description=self.paginas[self.index],
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"Página {self.index+1}/{len(self.paginas)}")
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
    async def anterior(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index == 0:
            return await interaction.response.send_message("⚠️ Primera página", ephemeral=True)
        self.index -= 1
        await self.update(interaction)

    @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
    async def siguiente(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index >= len(self.paginas) - 1:
            return await interaction.response.send_message("⚠️ Última página", ephemeral=True)
        self.index += 1
        await self.update(interaction)

async def actualizar_registros():
    channel = bot.get_channel(REGISTROS_CHANNEL_ID)

    if channel is None:
        print("❌ Canal registros no encontrado")
        return

    paginas = generar_paginas()

    embed = discord.Embed(
        title="📊 REGISTROS DE CLIENTES",
        description=paginas[0],
        color=discord.Color.blue()
    )
    embed.set_footer(text=f"Página 1/{len(paginas)}")

    view = RegistrosView(paginas)

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
        return

    precio_val = float(precio.replace("€", "").replace(",", "."))

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
async def borrar_registro(ctx, user_id: str, *, filtro: str):
    if not es_owner(ctx):
        return

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

# ---------------- START ----------------
if not TOKEN:
    print("❌ ERROR: No hay DISCORD_TOKEN")
    exit()

keep_alive()
bot.run(TOKEN)
