# -*- coding: utf-8 -*-
"""
미드저니 프롬프트 생성기.
입력: data/heroes.json, items.json, nations.json, battles.json(monsters), design/palette_nations.json, 본 파일의 수작업 서술 테이블
출력: docs/appendix/C1_프롬프트_영웅.md, C2_프롬프트_몬스터.md, C3_프롬프트_아이템.md, C4_프롬프트_배경_UI_컷신.md, data/prompts.json

프롬프트 규칙 (docs/12 §12):
  [카테고리 프리픽스] + [대상 서술] + [출신/국가 팔레트] + [카테고리 서픽스] --sref <앵커> --ar .. --stylize ..
  --sref 코드는 앵커 세트 확정 후 치환. 같은 영웅의 초상/전신/유닛 시트는 --cref <초상 URL>로 연결.
"""
import json, os
from collections import OrderedDict

ROOT = os.path.join(os.path.dirname(__file__), "..")
D = lambda n: json.load(open(os.path.join(ROOT, "data", n), encoding="utf-8"))
heroes = D("heroes.json"); items = D("items.json"); nations = D("nations.json"); battles = D("battles.json"); traits = D("traits.json")
PAL = json.load(open(os.path.join(ROOT, "design", "palette_nations.json"), encoding="utf-8"))
OUT = os.path.join(ROOT, "docs", "appendix")
os.makedirs(OUT, exist_ok=True)

MOOD = "painterly digital illustration, stylized dark fantasy, ash-grey atmosphere with ember-orange accents, dramatic rim light, muted palette with one saturated accent, cinematic composition, high-end mobile RPG splash art quality, clean readable silhouette, no text"
NEG = "--no text, watermark, logo, signature, frame, border, blurry, extra limbs, deformed hands"
SREF = {"portrait": "<SREF_PORTRAIT>", "standing": "<SREF_PORTRAIT>", "unit": "<SREF_UNIT>", "monster": "<SREF_UNIT>", "item": "<SREF_ITEM>", "bg": "<SREF_BG>", "cutscene": "<SREF_BG>", "ui": "<SREF_UI>"}

# ───────── 출신(종족·문화) 시각 토큰 ─────────
ORIGIN_LOOK = {
    "astel": "human knight-kingdom aesthetic, polished steel plate with blue tabard and silver lily heraldry, medieval western European court",
    "valheim": "northern human warrior culture, fur-lined leather and iron, braided hair, runic tattoos, frost on breath, viking-inspired",
    "sairam": "eastern empire aesthetic, lacquered samurai armor or kimono-inspired robes, cherry blossom motifs, ink-black and vermilion",
    "karna": "desert sultanate aesthetic, flowing silk, brass jewelry, turquoise inlays, sand-worn cloth, Middle-Eastern inspired",
    "lies": "maritime league aesthetic, weathered sailor and pirate garb, rope and brass, sea-salt stained leather, teal and rust red",
    "elowen": "elven forest-kingdom aesthetic, pointed ears, leaf-and-bark armor, living wood ornaments, moss green and firefly glow",
    "grandur": "dwarven mountain-kingdom aesthetic, stout proportions, braided beards, riveted bronze armor, rune-engraved metal, forge glow",
    "neos": "hidden hi-tech civilization aesthetic, sleek titanium armor plates, cyan holographic HUD elements, clean sci-fi lines mixed into a dark fantasy world",
    "nox": "necromantic kingdom aesthetic, black iron and bone ornaments, pale skin, violet-black robes, green phosphorescent accents",
    "celestia": "sky-island high-magic aesthetic, white and gold mage robes, floating star sigils, violet mana crystals, scholarly elegance",
    "dragonkin": "humanoid dragonkin, subtle scales on cheeks and forearms, small horns, slit pupils, scale-pattern armor, draconic color tied to their dragon",
    "torga": "tribal federation aesthetic, orc or beastfolk features, hide and bone armor, war paint, trophies, ochre and bone white",
    "lumen": "holy theocracy aesthetic, ivory and gold vestments or paladin plate, stained-glass motifs, halo-like backlight",
    "freelancer": "mercenary aesthetic, mismatched practical gear, grey wolf guild badge, worn leather and dented steel, road-dusted",
}
CLASS_LOOK = {
    "knight": "heavy armored frontline knight with a tower shield and sword", "warrior": "muscular bruiser with a great axe or two-handed weapon",
    "assassin": "lithe assassin with twin daggers, hooded, shadowed face", "ranger": "archer with a longbow and quiver, keen eyes",
    "mage": "spellcaster with a staff or tome, glowing magic circle", "priest": "healer with a censer or holy symbol, soft healing light",
    "guardian": "stalwart guardian with a massive shield and banner", "duelist": "swift duelist with paired blades mid-flourish",
    "summoner": "summoner with a familiar or spirit at their side", "artillerist": "long-range artillerist with a siege weapon or cannon",
    "shaman": "shaman with totems, bones and curse-smoke", "bard": "bard with an instrument, charismatic pose",
    "dragoon": "winged-mount rider with a lance, flight harness, wind-swept", "engineer": "engineer with tools, gears and a small turret",
}
TIER_LOOK = {1: "simple practical gear, few ornaments", 2: "well-made gear with modest ornaments", 3: "fine gear with faction insignia and one magical element",
             4: "ornate master-tier gear, glowing magical accents", 5: "legendary regalia, elaborate silhouette, powerful aura effects"}

# ───────── 영웅별 서술 (영문 시각 키워드: 성별·연령·외형·핵심 소품). 수작업. ─────────
HERO_DESC = {
 "로이드 하트윈": "middle-aged man, grizzled paladin commander, white-gold plate, kite shield with lily, resolute weary eyes",
 "세드릭 아스텔": "young prince in his late twenties, blue-and-silver royal armor, wyvern-rider harness, confident smirk, wind-blown hair",
 "가웨인 로스": "veteran knight in his fifties, scarred face, silver shield with wolf dent marks, battered blue tabard",
 "에드릭 몬타뉴": "court mage, forties, dark blue robe with silver embroidery, monocle, holding a glowing lantern-orb",
 "리젤": "young woman royal assassin, hooded, pale face, dagger hidden under cloak, cold calm eyes",
 "하워드 크레인": "old ballista sergeant, sixties, grey mustache, trembling but precise hands, shoulder-mounted crossbow ballista",
 "마리엘": "young woman royal healer, white-blue habit, gentle expression, glowing hands",
 "길버트 홀": "royal chief engineer, forties, leather apron over blue coat, blueprint scroll, gate-crossbow turret",
 "브랜든 홀트": "border garrison captain, thirties, practical chainmail, broad shoulders, halberd",
 "엘레나 베일리": "young woman falconer, leather glove with a hunting hawk, green-blue cloak",
 "올란도": "wandering bard, thirties, lute, flamboyant blue scarf, satirical grin",
 "토마스 플레처": "teenage apprentice archer, farmer's son, simple shortbow, freckles",
 "핀": "teenage squire, oversized hand-me-down armor, eager expression, short sword",
 "아그네스": "elderly herb witch, hunched, herb pouches, gnarled staff, kind but sharp eyes",
 "시그룬 아이언브로우": "warrior queen in her forties, iron crown, wolf-fur mantle over scale armor, two-handed sword, fierce",
 "그림힐드": "ancient norn seer, very old woman, rune-carved staff, white braids, storm clouds behind",
 "비요른 프로스트": "huge bearded bodyguard, forties, round frost-rimed shield, bear fur",
 "하랄드 울프스킨": "wolf-pelt rider, thirties, frost wyvern harness, spear, ice crystals on beard",
 "에이나르": "berserker with twin axes, shirtless under fur, scars, wild eyes, no pain",
 "아스트리드": "hawk-eyed huntress, twenties, white-grey hunting leathers, longbow, snow",
 "토르발드": "shield-wall leader, thirties, broad rectangular shield, clan tattoos",
 "올라프": "rune priest, fifties, bone runes necklace, blue painted face",
 "스카디": "shadow-footed huntress, twenties, white camouflage cloak, daggers",
 "우나": "young wolf-tamer girl with a grey wolf companion, fur hood",
 "군나르": "massive stone-thrower, boulder on shoulder, simple hide clothes",
 "이바르": "young self-taught ice mage, fisherman's clothes, frost on fingertips",
 "레이프": "young skald with a lyre, singing, wool cloak",
 "헬가": "blacksmith woman, forties, soot-stained, hammer, portable siege crossbow",
 "카게토라": "sword saint, fifties, plain dark kimono, single katana, serene lethal stillness",
 "호렌": "grand onmyoji, ageless, white-and-black ceremonial robe, paper shikigami floating, star chart",
 "하야테": "ninja, late twenties, dark shinobi garb, wind-swept, shadow clones",
 "아카네": "yumi archer woman, twenties, cherry-petal kimono armor, tall bow",
 "유키노": "shikigami girl, teenage, paper dolls animated around her",
 "노부타다": "heavy samurai in full ornate armor, kabuto helmet, immovable stance",
 "사쿠야": "young shrine maiden, red-and-white miko robes, purification bells",
 "겐조": "matchlock gunner, thirties, conical hat, arquebus",
 "류자키": "ronin, thirties, unkempt, worn kimono, iaido stance",
 "쿠로": "gloomy spirit-binder, pale, black robe, wraith hovering behind",
 "타츠마": "young dragoon cavalryman, lacquered red armor, lance, wyvern",
 "고로": "ashigaru captain, forties, bamboo-spear, simple jingasa helmet",
 "코하루": "young shamisen player girl, festival kimono, playing on a battlefield",
 "히데요": "gunpowder artisan, fifties, fireworks-turret, burn scars",
 "자파르": "assassin guild master, forties, black-and-turquoise silk, curved daggers, sand swirling",
 "샤흐라자드": "storyteller sorceress, thirties, veiled, lamp-genie manifesting behind her, golden jewelry",
 "라시드": "desert lion guard captain, broad, scimitar, lion-mane cloak",
 "나디아": "sand sorceress, twenties, swirling sandstorm veil, turquoise eyes",
 "오마르": "eccentric camel-cannoneer, mustache, small brass cannon",
 "타리크": "mamluk knight, former slave, chain-and-lamellar armor, round shield",
 "라일라": "flame sorceress, twenties, ember-red silk, fire spirit",
 "카림": "sand wyvern rider, goggles, scarf, dune wyvern",
 "파리드": "nomad horse archer, composite bow, headscarf",
 "아미라": "oasis healer woman, blue water jar, palm leaf",
 "야스민": "dancer-swordswoman, twin scimitars, flowing dance silks",
 "하산": "bazaar guard, earnest young man, spear and small shield",
 "바바 알리": "old market storyteller, white beard, colorful rugs",
 "이드리스": "boy mechanic, goggles, gear-trap gadget",
 "카탈리나 벨": "admiral woman, forties, teal naval coat, tricorn, spyglass, cannons behind",
 "트리톤 바르": "merfolk king, scaled skin, coral crown, trident, deep-sea majesty",
 "블랙 모건": "pirate king, forties, black coat, gold teeth grin, cutlass",
 "멜로디아": "siren woman, iridescent fins on ears, sea-foam dress, singing",
 "요나": "kraken-caller, haunted man, tentacle scars, harpoon",
 "브루노": "giant boatswain swinging an anchor, tattoos",
 "루시아": "street-urchin pickpocket girl, teenage, throwing knives",
 "바실": "fleet surgeon, forties, rum bottle, bloody apron",
 "마르코": "young naval lieutenant, teal uniform, shield charge",
 "엘사": "merchant-ship crossbow guard woman, practical leathers",
 "가브리엘": "storm navigator man, lightning in the sky, oilskin coat",
 "마마 조": "voodoo priestess, old woman, bone beads, curse doll",
 "톰": "boy sea-serpent rider, barefoot, riding a small sea serpent",
 "올리버": "shipwright engineer, thirties, deck turret, sawdust",
 "실바나 아엘린": "elven queen, ageless, living-wood crown, world-tree bow, ethereal",
 "오리엘": "arch-druid, ancient elf, bark skin, antler staff, mossy robes",
 "루미엘": "starlight mage elf woman, silver hair, falling-star staff",
 "니아": "forest shadow elf, leaf camouflage, thorn daggers",
 "티아라": "young elf spirit-summoner girl with glowing forest spirits",
 "엘라리온": "elf wind-dancer swordsman, twin curved blades, flowing hair",
 "브람블": "thorn druid, old elf covered in bramble vines",
 "파엘": "elf griffon rider, feather-lined armor, griffon",
 "카엘렌": "elf forest knight, bark-wood shield, leaf plate",
 "모스": "walking treant, mossy ancient tree creature, gentle eyes",
 "아르보른": "ancient tree guardian, gnarled roots, bark shield",
 "리안": "young elf longbowman apprentice",
 "피오": "elf boy with a wooden flute, birds around him",
 "에린": "elf woodcarver woman, thorn-trap device",
 "토르딘 아이언핸드": "dwarf king, steel prosthetic hand, massive steam turret, crown of gears",
 "브롬 스톤하트": "dwarf rune-knight, full rune-engraved armor, tower shield",
 "두린": "dwarf berserker, mountain-splitting axe, wild beard",
 "그림로크": "dwarf cannon-artisan, steam cannon, goggles",
 "발더": "dwarf shield-wall guardian, immense square shield",
 "헬라": "dwarf crossbow markswoman, tunnel lantern",
 "모르딘": "dwarf rune-engraver, glowing chisel, rune explosions",
 "피를리": "dwarf golem-maker with a stone golem friend",
 "노리": "dwarf tunnel-infiltrator, drill-pick, dusty",
 "베르나": "dwarf rune-priestess, healing runes",
 "코린": "dwarf twin-hammer duelist",
 "핌": "young dwarf furnace-mage, lava orb",
 "보핀": "jolly dwarf beer-singer with a tankard",
 "달라": "dwarf girl with steam-powered wings, goggles",
 "ORB-9": "orbital bombardment unit, sleek white-titanium humanoid drone, cyan lens eye, satellite link antenna",
 "윌로우 하인즈": "chief scientist woman, forties, white lab coat over titanium harness, holographic drone turret",
 "AEGIS-1": "defense automaton, heavy white-cyan armored android, force-field shield",
 "이오": "cyborg plasma mage, implants on temples, plasma orb",
 "GHOST-3": "stealth infiltration unit, matte black android, optical camouflage shimmer",
 "노바": "sniper-drone operator woman, railgun, targeting drone",
 "MEDIC-7": "field medical android, white with cyan cross, nano-mist emitters",
 "카이": "drone controller youth, ten small combat drones, hologram gloves",
 "크루거": "exo-suit infantry man, bulky power-armor, power fist",
 "BLADE-2": "combat android with a monomolecular sword",
 "젠": "EMP disruptor soldier woman, electric gauntlets",
 "BULWARK": "budget shield robot, boxy, large riot shield",
 "리듬": "holographic idol singer, translucent cyan-pink hologram body, stage lights",
 "렉스": "jetpack trooper, visor, thruster flames",
 "말라키": "arch-lich, skeletal face under hood, violet-black robes, green soul-fire crown",
 "모르가나 녹스": "necromancer queen, pale, black crown, bone throne, undead legion behind",
 "세르반": "vampire duke, aristocratic, blood-red cravat, fangs",
 "헥사": "curse-witch, plague doctor mask, green vapors",
 "모르드": "death knight, black full-plate, no face visible, green eye glow",
 "그롤": "young ghoul brute, grey skin, oversized jaw",
 "네리사": "dark priestess, black veil, shadow healing hands",
 "카라즈": "bone-dragon rider, skeletal dragon mount",
 "라트": "skeleton archer, rotting bow",
 "오사": "bone golem, built of stacked skulls and femurs",
 "라바인": "sword-ghost, translucent swordsman possessing a blade",
 "피트": "plague-jar throwing ghoul",
 "울라": "banshee queen, wailing spectral woman, long white hair",
 "이고르": "corpse-assembler hunchback with a flesh turret",
 "오리온 셀레스티아": "archmage, ageless, white-gold robes, supernova halo, star-crystal staff",
 "리라": "time-chorister woman, singing, clock-like halos, violet-gold",
 "엘라라": "starlight priestess, gentle, star-dust robes",
 "아틀라스": "star-guardian, huge armored figure holding a sky-vault shield",
 "아스트라": "constellation summoner, star-beast made of light",
 "세레노": "sky-knight, gravity sword, floating armor pieces",
 "베가": "starlight archer woman, meteor arrows",
 "칼리스토": "astrologer, star charts, cursed constellation",
 "리스": "void assassin, space-fold blur, dark violet",
 "아리아": "spellblade duelist woman, mana-sword",
 "테오": "arcane artillerist, mana cannon",
 "피오나": "apprentice spellsword girl, oversized sword",
 "밀로": "cloud-drake apprentice rider boy",
 "엘리엇": "magitech engineer student, mana turret",
 "아젤리아": "azure dragon queen in humanoid form, blue scales, frost breath, regal, horns, icy wings hint",
 "이그니스": "crimson dragon general in humanoid form, red-black scales, burning wings, scarred, defected",
 "갈란드": "golden dragon warrior, gold scales, bare-fisted brawler",
 "세리스": "white dragon knight, pearl scales, egg-guardian shield",
 "베릴": "green dragon healer, jade scales, caring for dragon eggs",
 "카시안": "half-dragon young man, black scales on forearms, mercenary gear, grey-wolf badge, intense amber eyes, son of the black dragon",
 "니르": "shadow dragon assassin, dark violet scales",
 "라케아": "dragon-scale archer, arrows tipped with her own scales",
 "세레나": "dragon shrine maiden, scale-patterned robes, curse runes",
 "피피": "young dragonkin girl cradling a hatchling dragon",
 "드라코": "dragonfire cannoneer, fire-breath cannon",
 "타르": "young dragonkin nest guard, scale shield",
 "리리카": "dragonkin singer girl, dragon-tongue song visualized",
 "보르": "dragonsteel smith, scale-forge turret",
 "그룸 블러드액스": "orc great chieftain, massive, blood axe, skull trophies, war paint",
 "카쉬": "orc grand shaman, ancestor spirits, bone staff",
 "라가르": "orc twin-axe gladiator, arena champion",
 "타이라": "tiger-beastfolk archer woman, striped fur",
 "볼그": "orc wyvern rider, trampling charge",
 "토르토": "tortoise-beastfolk shield warrior, shell as shield",
 "미르카": "beast tamer woman with a pack of beasts",
 "보르그": "four-meter giant stone-thrower",
 "샤": "leopard-beastfolk assassin, spotted fur",
 "우르사": "bear-beastfolk healer, big warm matron",
 "람": "rhino-beastfolk shield guardian",
 "지크": "goblin pyromancer, fire orb, mischievous",
 "두둠": "goblin war-drummer",
 "스니크": "goblin chief engineer, scrap mega-turret",
 "요한나 루멘": "holy saint, young woman, white-gold vestments, resurrection light, serene sorrow",
 "가브리엘 아르망": "grand paladin, fifties, white-gold full plate, holy barrier",
 "레이븐": "inquisitor, black-and-gold coat, judgment blade, raven motif",
 "세라피나": "angel-summoner nun, summoned angel behind",
 "바르톨로": "cathedral gate guard, big shield",
 "루시우스": "holy-light mage, radiant judgment",
 "클레어": "holy archer nun, sacred arrows",
 "안젤로": "choirmaster, hymn aura",
 "마르틴": "pilgrim warrior, mace, road-worn",
 "노엘": "holy sword trainee youth",
 "이사도라": "exorcist woman, chains and holy seals",
 "피터": "church arquebusier",
 "로렌": "griffon apprentice rider",
 "도미닉": "cathedral master architect, relic turret",
 "바르토스": "mercenary guild master, fifties, grey wolf mantle, scarred, two-handed sword, Leon's mentor",
 "레드 하울": "bounty hunter, red coat, long rifle, wide hat, wanted posters",
 "브루트": "silent giant mercenary with an enormous axe",
 "윌라": "runaway mage woman, tattered academy robe",
 "다리우스": "mercenary wyvern rider, coin pouch",
 "오스왈드": "old knight in dented, rusted armor, dignified",
 "잭 스캐빈": "thief with a lockpick and dagger, smirk",
 "헬레나": "field surgeon woman, medical bag",
 "로완": "forest hunter, poison arrows",
 "에스메": "wandering fortune-teller woman, tarot cards",
 "티모": "traveling inventor with a cart of gadgets, portable turret",
 "벤": "rookie shield-bearer, nervous",
 "포피": "girl with stray dogs",
 "로지": "theater diva singer, brilliant stage dress",
}
SPECIAL = [
    ("P000", "레온 바르크", "freelancer", "duelist", 3, "protagonist, wandering mercenary man in his late twenties, grey wolf guild cloak, dented steel breastplate, two swords, determined tired eyes, stubble", None),
    ("NPC1", "엘리아", "freelancer", "priest", 3, "the protagonist's lover, village healer woman in her twenties, simple linen dress with herb satchel, warm eyes, faint dragon-blood glow in her hands",
     "border-village healer, humble linen and wool, no armor, herb pouch, soft candlelight"),
]

# ───────── 몬스터 서술 ─────────
MON_DESC = {
 "bandit_sword": "bandit swordsman, ragged leather", "bandit_bow": "bandit archer, hooded", "bandit_boss": "bandit chief, scarred, big saber", "merc_spear": "mercenary spearman, dented helm",
 "merc_knight": "mercenary knight, mismatched plate", "merc_mage": "mercenary mage, cheap staff", "merc_captain": "mercenary captain, black-hand insignia", "royal_inf": "royalist infantry, blue tabard",
 "royal_knight": "royalist knight, lily heraldry", "royal_crossbow": "royalist crossbowman", "royal_general": "royalist general, ornate blue-gold plate", "zealot": "fanatic zealot with a flail",
 "inquisitor": "inquisitor in black, judgment dagger", "holy_guard": "papal guard, white-gold halberd", "pirate": "pirate deckhand, cutlass", "pirate_gunner": "pirate gunner, swivel gun",
 "pirate_captain": "pirate captain, tricorn", "sea_serpent": "sea serpent, teal scales, fins", "kraken_spawn": "kraken spawn, tentacled mass", "deep_horror": "deep-sea horror, bioluminescent abyssal creature",
 "clan_warrior": "northern clan warrior, axe and fur", "clan_berserk": "clan berserker, blood-painted", "frost_giant": "frost giant, ice-crusted colossus", "ice_troll": "ice troll, blue hide",
 "wolf": "grey wolf", "dire_wolf": "dire wolf, huge, scarred", "sand_raider": "desert raider on foot, scarf and scimitar", "sand_worm": "giant sand worm, ringed maw",
 "mummy": "bandaged mummy guardian", "mummy_lord": "mummy lord, golden death mask", "sultan_guard": "sultan's guard, brass armor", "djinn": "corrupted djinn, smoke body, burning eyes",
 "orc_grunt": "orc grunt, crude cleaver", "orc_shaman": "orc shaman, totem", "ogre": "ogre, club", "troll": "troll, regenerating hide",
 "goblin": "goblin, dagger", "goblin_eng": "goblin bomber, bomb satchel", "beast_boar": "raging boar", "beast_tiger": "sabertooth tiger",
 "horse_archer": "steppe horse archer", "raider_cav": "steppe raider cavalry", "barrow_wight": "barrow wight, spectral", "ninja": "ninja, black garb",
 "ashigaru": "ashigaru foot soldier, bamboo spear", "samurai": "samurai, lacquered armor", "shogun_general": "shogun's general, horned kabuto", "onryo": "onryo vengeful ghost, long black hair",
 "oni": "oni demon, red skin, iron club", "dark_sprite": "corrupted forest sprite", "spider": "giant forest spider", "withered_treant": "withered treant, dead bark",
 "logger": "logger intruder, axe", "forest_horror": "forest horror, antlered beast", "mine_crawler": "mine crawler, pale insectoid", "rogue_golem": "rogue stone golem, cracked runes",
 "deep_savage": "underground savage, fungus-painted", "ancient_automaton": "ancient automaton, bronze and rune-light", "lava_elemental": "lava elemental", "frost_witch": "frost witch, icy veil",
 "sea_wolf": "sea-wolf pirate", "ice_giant": "drift-ice giant", "ghost_ship": "ghost ship crewman, spectral sailor", "deep_abomination": "deep abomination, anglerfish-like",
 "fallen_merfolk": "corrupted merfolk", "sea_wraith": "sea wraith, drowned spirit", "pixie": "mischievous pixie", "illusion": "illusion horror, shifting faces",
 "dream_eater": "dream eater, moth-like nightmare", "mist_ghost": "mist ghost", "lizard_warrior": "lizardfolk warrior, obsidian club", "giant_reptile": "giant reptile, armored",
 "poison_frog": "poison frog swarm", "man_eater_plant": "man-eating plant, toothed maw", "raptor": "raptor, feathered", "tyrant_lizard": "tyrant lizard, tyrannosaur-like",
 "skeleton": "skeleton soldier", "skeleton_archer": "skeleton archer", "ghoul": "ghoul", "wraith": "wraith, hooded void",
 "vampire_knight": "vampire knight, crimson plate", "lich_servant": "lich's servant, chained necromancer", "bone_dragon": "bone dragon, skeletal wings", "bat_swarm": "bat swarm",
 "gargoyle": "gargoyle, stone wings", "blood_ghoul": "blood-starved ghoul", "obsidian_golem": "obsidian golem, lava cracks", "fire_lizard": "fire lizard",
 "sulfur_horror": "sulfur horror, yellow smoke", "fallen_elementalist": "corrupted elementalist", "war_bot": "rogue war robot, battered", "wasteland_raider": "wasteland raider, scrap armor, rifle",
 "mutant": "mutant creature, extra limbs", "defense_droid": "defense droid, white-cyan", "proto_weapon": "prototype war machine, quadruped, railguns", "laser_turret": "laser turret",
 "arcane_construct": "rogue arcane construct, floating crystal", "void_beast": "void beast, star-speckled darkness", "fallen_mage": "corrupted sky mage", "star_golem": "star guardian golem, marble and gold",
 "spire_guardian": "world-spire guardian, towering ancient construct", "nest_guardian": "dragonkin nest guardian, scale armor", "corrupt_wyvern": "corrupted wyvern", "dragon_ghost": "dragon ghost, translucent",
 "ash_soldier": "Ashwing soldier, black scale armor, ember eyes", "ash_archer": "Ashwing archer", "ash_wyvern": "flame wyvern, burning wings", "ash_dragonkin": "Ashwing dragonkin elite, black-red scales",
 "ash_mage": "Ashwing shaman, ash-magic", "ash_general": "Ashwing general, towering black-red dragonkin in obsidian plate, burning crown", "ash_spy": "Ashwing spy, hooded, scale glint",
 "gladiator": "arena gladiator", "smuggler": "smuggler, crossbow", "swamp_horror": "swamp horror", "mine_horror": "mine horror, pale burrower", "rebel": "rebel militia", "cult_mage": "black-magic cultist", "mist_horror": "mist horror",
}
MON_NATION = {}  # 몬스터 → 대표 국가(팔레트) : FACTION_POOL 역추적
for b in battles["battles"]:
    if b["kind"] != "regional": continue
    for u in b["enemy"]["units"]:
        MON_NATION.setdefault(u["unit"], b["nation"])
    if b["enemy"]["boss"]: MON_NATION.setdefault(b["enemy"]["boss"]["unit"], b["nation"])

# ───────── 지역 배경 서술 (국가별 5지역) ─────────
REGION_DESC = {
 "bromel": ["cobbled guild street with wolf banners and bounty boards", "sand-floored arena ring with wooden stands", "rain-slick slum alleys with hanging lanterns", "forest road at dusk with a broken cart", "merchant highway with caravans and milestones"],
 "astel": ["grand royal capital with blue banners and a white keep", "burned border village of Haron, smoke and charred timber", "wide western plains with armies' tents on the horizon", "golden wheat fields and granaries", "northern fortress line of stone towers"],
 "mir": ["ducal castle on a hill", "terraced vineyards at golden hour", "river village with watermills", "sacked monastery, broken stained glass", "border forest with royalist scouts"],
 "harben": ["marquis citadel under siege banners", "reed marsh with mist and rotting piers", "abandoned mine entrance, rusted carts", "mercenary camp of tents and campfires", "stone border bridge over a swollen river"],
 "lumen": ["cathedral square with towering spires and pilgrims", "pilgrim road lined with shrines", "inquisition hall, iron chairs and candles", "relic catacombs with glowing reliquaries", "monastery on a mountain ridge"],
 "lies": ["bustling harbor of Porto Lies with ships and cranes", "pirate island Tortuga, taverns on stilts", "storm strait with towering waves and lightning", "merchant sea lane at sunset", "shipwreck graveyard, broken hulls on reefs"],
 "valheim": ["fjord coast with longships and snow", "endless snowfield under pale sun", "frost mountains, ice-bound passes", "clan hall village of timber and runes", "ice cave with blue crystal walls"],
 "karna": ["domed desert capital Zahra, minarets, brass", "caravan route across red dunes", "oasis city with palms and pools", "forgotten pyramid half-buried in sand", "assassin fortress carved into a cliff"],
 "torga": ["great grassland with tribal totems", "bone mountain of giant skeletons", "goblin warren tunnels with scrap", "beastfolk forest with hide tents", "arena hill ringed with skull poles"],
 "kurgan": ["northern steppe with yurts and horse herds", "horse market with felt banners", "sacred lake mirroring the sky", "burial mounds under storm clouds", "wooden border fortress on the steppe"],
 "sairam": ["imperial capital Kyotora with vermilion gates", "cherry blossom road, petals in the air", "shogun's black castle at night", "misty mountain shrine path", "ghost forest with floating lanterns"],
 "elowen": ["world-tree city built into a colossal tree", "ancient forest with giant roots", "spirit spring with glowing water", "thorn thicket zone, bramble walls", "withered forest, grey dying trees"],
 "grandur": ["Iron Hall, vast underground dwarven hall with statues", "forge district with rivers of molten metal", "deep mine shafts with crystal veins", "rune vault with glowing engraved pillars", "ancient ruins layer, pre-cataclysm machinery"],
 "frost_isles": ["white harbor with whalers' boats", "whalebone coast, giant ribs on the beach", "frost witch tower on a crag, aurora", "drift ice field with seals", "silent island shrouded in snow fog"],
 "tiama": ["coral palace of the merfolk, pearl light", "deep trench with bioluminescence", "sunken human city under water", "current tunnels of swirling water", "kraken nest, giant tentacles in darkness"],
 "veil": ["fae mist court with floating lanterns", "illusion maze of hedges and mirrors", "dream lake reflecting a different sky", "giant mushroom forest with glowing caps", "village frozen in time, clocks stopped"],
 "zyros": ["jungle edge with vines and ruins", "poison swamp with yellow haze", "stone pyramid city of the lizardfolk", "giant tree zone with hanging bridges", "dinosaur valley with roaring beasts"],
 "nox": ["black castle Nox under green-lit fog", "fields of the dead, rising skeletons", "mist swamp with drowned trees", "vampire estate with red windows", "forbidden archive of chained books"],
 "twilight": ["fortress ramparts at eternal dusk", "blood-red vineyard terraces", "ossuary of stacked bones and candles", "bat caves with dripping stalactites", "twilight village with closed shutters"],
 "makab": ["obsidian city with lava-lit streets", "lava lake with stone bridges", "sulfur fields with yellow vents", "golem workshop with half-built colossi", "heart of the spirit, glowing core cavern"],
 "neos": ["grey ash wasteland with rusted war machines", "dome defense line with turrets and drones", "dome city interior, clean white towers and holograms", "underground lab with glass tanks", "decommissioned armory with dormant mechs"],
 "celestia": ["floating sky city of white marble", "magic academy with floating books", "star observatory with giant astrolabe", "edge of the void, islands breaking into stars", "sanctum of the World Spire, a colossal glowing seal"],
 "drakestan": ["dragon nest entrance between twin peaks", "egg cavern with giant eggs on warm stone", "dragon graveyard of enormous bones", "sky peak above the clouds", "ancient dragon temple with murals"],
 "ashfell": ["ash wastes under a burning sky", "burning fortress of black stone", "dragon-claw canyon with lava veins", "outskirts of the ash throne, armies gathering", "the World Spire cracking, the heart glowing beneath"],
}

CUTSCENES = [
 ("CS-00", 0, "prologue: a border village at night engulfed in flames, a black dragon's silhouette against the moon carrying a woman away"),
 ("CS-01", 1, "Leon kneeling in the ashes of Haron holding a dragon scale shard, dawn"),
 ("CS-02", 1, "Bromel arena: Leon meets Kasian, a half-dragon mercenary, dust and torchlight"),
 ("CS-03", 1, "Prince Cedric and Leon on a castle wall at Camelin, wyverns circling"),
 ("CS-04", 1, "decisive battle at Haron: Leon faces Ashwing general Skar amid burning palisades"),
 ("CS-05", 2, "Saint Johanna freed from the inquisition hall, holy light breaking through chains"),
 ("CS-06", 2, "Admiral Catalina's fleet defending Porto Lies at dawn"),
 ("CS-07", 2, "Queen Sigrun's duel with Leon in a snow-covered clan hall"),
 ("CS-08", 2, "assassin master Jafar breaking his contract in a desert fortress at night"),
 ("CS-09", 2, "sword saint Kagetora waiting under falling cherry blossoms"),
 ("CS-10", 2, "the world tree withering, Queen Sylvana touching its bark"),
 ("CS-11", 2, "dwarven ruins revealing ancient machinery blueprints, Thordin's steel hand on the wall"),
 ("CS-12", 2, "naval decisive battle against the Ashwing fleet, heroes of seven kingdoms under one banner"),
 ("CS-13", 3, "merfolk guiding the party through underwater current tunnels"),
 ("CS-14", 3, "the fae queen's mist court, time-frozen villagers"),
 ("CS-15", 3, "forbidden archive of Nox, Queen Morgana offering an alliance"),
 ("CS-16", 3, "the Neos dome opening, scientist Willow Heinz revealing the World Spire as a control device"),
 ("CS-17", 3, "Archmage Orion confessing at the sanctum, Ashwing shaman attacking the spire"),
 ("CS-18", 4, "Kasian leading the party into the dragon nest, giant unhatched eggs"),
 ("CS-19", 4, "temple murals showing Isela and the black dragon Vargrad in love, a thousand years ago"),
 ("CS-20", 4, "Ignis the crimson dragon turning against the Ashwing, Azelia declaring her break with her brother"),
 ("CS-21", 5, "armies of the world gathering on the ash plains before the throne"),
 ("CS-22", 5, "Elia bound on the altar as the Spire cracks, Leon reaching out"),
 ("CS-23", 5, "final battle: Leon versus the black dragon Vargrad amid the breaking Spire"),
 ("CS-24", 5, "epilogue: the first dragon egg hatching in Drakestan, Leon and Elia watching"),
]


def pal(nkey):
    p = PAL[nkey]
    return f"color palette {p['primary']} primary, {p['secondary']} secondary, {p['accent']} accent, materials {p['material']}, lighting {p['light']}"


ORIGIN_NATION = {"astel": "astel", "valheim": "valheim", "sairam": "sairam", "karna": "karna", "lies": "lies", "elowen": "elowen", "grandur": "grandur", "neos": "neos", "nox": "nox",
                 "celestia": "celestia", "dragonkin": "drakestan", "torga": "torga", "lumen": "lumen", "freelancer": "bromel"}


def hero_prompts(h):
    desc = HERO_DESC.get(h["name_ko"], "")
    nk = ORIGIN_NATION[h["origin"]]
    look = h.get("_look") or ORIGIN_LOOK[h["origin"]]
    parts = [desc, h.get("title") or "", CLASS_LOOK[h["class"]], look, TIER_LOOK[h["tier"]], pal(nk)]
    core = ", ".join(x for x in parts if x)
    return OrderedDict([
        ("portrait", f"character portrait, bust shot, three-quarter view, face fills half the frame, {core}, simple gradient background in the faction primary color with faint ash particles, {MOOD} --ar 1:1 --stylize 200 --sref {SREF['portrait']} {NEG}"),
        ("standing", f"full-body character illustration, standing pose showing the whole figure head to toe, weapon visible, {core}, plain neutral dark background for cutout, {MOOD} --ar 2:3 --stylize 200 --sref {SREF['standing']} --cref <PORTRAIT_URL> --cw 70 {NEG}"),
        ("unit", f"stylized chibi game character design sheet, 2.5-head proportion, front three-quarter view and side view, flat even lighting, bold readable silhouette, thick clean outlines, {core}, solid light-grey background, 2D mobile autobattler unit, {MOOD.replace('cinematic composition, ', '')} --ar 3:2 --stylize 120 --sref {SREF['unit']} --cref <PORTRAIT_URL> --cw 60 {NEG}"),
    ])


def monster_prompts(m):
    nk = MON_NATION.get(m["key"], "bromel")
    boss = m["tier"] >= 4
    core = f"{MON_DESC.get(m['key'], m['name_ko'])}, {CLASS_LOOK[m['class']]}, {pal(nk)}"
    out = OrderedDict([("unit", f"stylized chibi game creature design sheet, {'2.5-head' if m['tag'] in ('인간','용족','오크','고블린','언데드') else 'creature'} proportion, front three-quarter view and side view, flat even lighting, bold readable silhouette, thick clean outlines, {core}, solid light-grey background, 2D mobile autobattler enemy unit, {MOOD.replace('cinematic composition, ', '')} --ar 3:2 --stylize 120 --sref {SREF['monster']} {NEG}")])
    if boss:
        out["portrait"] = f"boss portrait, bust shot, menacing, {core}, dark gradient background, {MOOD} --ar 1:1 --stylize 220 --sref {SREF['portrait']} {NEG}"
        out["fullbody"] = f"boss creature full illustration, dramatic low angle, {core}, atmospheric environment hint, {MOOD} --ar 16:9 --stylize 250 --sref {SREF['bg']} {NEG}"
    return out


COMP_MOTIF = {"C01": "a straight steel longsword", "C02": "an arcane rod with a floating crystal", "C03": "a wide leather belt with a giant's buckle", "C04": "a chainmail vest", "C05": "a spirit-woven cloak",
              "C06": "a recurve bow", "C07": "a crystal teardrop", "C08": "a pair of lucky gloves", "C09": "a vampire fang amulet", "C10": "a glowing star fragment", "C11": "a single dragon scale", "C12": "a hero's crest medallion"}
CAT_STYLE = {"component": "simple iconic object", "completed": "iconic fantasy item combining two motifs", "radiant": "iconic fantasy item radiating golden light, upgraded ornate version",
             "artifact": "legendary unique relic with lore detail", "support": "banner, totem or support tool", "national": "national specialty object with cultural ornament",
             "emblem": "faction emblem medallion", "consumable": "potion, scroll or token", "material": "crafting material"}


def item_prompt(it):
    motif = ""
    if it.get("recipe"):
        motif = " combining " + " and ".join(COMP_MOTIF.get(r, r) for r in it["recipe"])
    nat = ""
    if it.get("nation"): nat = ", " + pal(it["nation"])
    stat = ", ".join(f"{k} {v}" for k, v in it.get("stats", {}).items())
    hooks = ", ".join(h["type"].replace("_", " ") for h in it.get("hooks", []))
    cat = CAT_STYLE[it["category"]]
    return (f"game item icon, {cat}, {it['name_en']}{motif}, visual hint of its effect ({hooks or stat or 'none'}), centered single object, three-quarter view, "
            f"studio lighting with ember rim light, rich material detail, solid very dark grey background, no hands, no character{nat}, {MOOD.replace('cinematic composition, ', '')} "
            f"--ar 1:1 --stylize 150 --sref {SREF['item']} {NEG}")


def main():
    prompts = {"heroes": [], "monsters": [], "items": [], "backgrounds": [], "cutscenes": [], "ui": []}
    # C1 영웅
    L = ["# 부록 C1. 미드저니 프롬프트 — 영웅 (196 + 레온·엘리아)", "", "자동 생성: `python tools/gen_prompts.py`. 각 영웅 3종(초상 1:1 / 전신 2:3 / 유닛 시트 3:2). `<SREF_*>`는 앵커 세트 확정 후 치환, `<PORTRAIT_URL>`은 확정된 초상 이미지 URL.", ""]
    ON = {o["key"]: o["name_ko"] for o in traits["origins"]}; CN = {c["key"]: c["name_ko"] for c in traits["classes"]}
    specials = [dict(id=i, name_ko=n, origin=o, **{"class": c}, tier=t, title="", skill={}, _desc=d, _look=lk) for i, n, o, c, t, d, lk in SPECIAL]
    for h in specials + heroes["heroes"]:
        if "_desc" in h: HERO_DESC[h["name_ko"]] = h["_desc"]
        ps = hero_prompts(h)
        prompts["heroes"].append({"id": h["id"], "name_ko": h["name_ko"], "prompts": ps})
        L += [f"## {h['id']} {h['name_ko']} ({ON[h['origin']]}·{CN[h['class']]}·T{h['tier']}{(' · ' + h['title']) if h.get('title') else ''})", ""]
        for k, v in ps.items(): L += [f"**{k}**", "", "```", v, "```", ""]
    open(os.path.join(OUT, "C1_프롬프트_영웅.md"), "w", encoding="utf-8").write("\n".join(L))
    # C2 몬스터
    L = [f"# 부록 C2. 미드저니 프롬프트 — 몬스터 ({len(battles['monsters'])})", "", "일반 몬스터: 유닛 시트 1종. 보스(계층 4~5): 유닛 시트 + 초상 + 전신.", ""]
    for m in battles["monsters"]:
        ps = monster_prompts(m); prompts["monsters"].append({"key": m["key"], "name_ko": m["name_ko"], "prompts": ps})
        L += [f"## {m['key']} {m['name_ko']} (T{m['tier']}·{m['class']})", ""]
        for k, v in ps.items(): L += [f"**{k}**", "", "```", v, "```", ""]
    open(os.path.join(OUT, "C2_프롬프트_몬스터.md"), "w", encoding="utf-8").write("\n".join(L))
    # C3 아이템
    L = ["# 부록 C3. 미드저니 프롬프트 — 아이템 (282)", "", "아이콘 512×512, 단색 어두운 배경 → 배경 제거 후 분류 테두리는 엔진에서 합성.", ""]
    for it in items["items"]:
        p = item_prompt(it); prompts["items"].append({"id": it["id"], "name_ko": it["name_ko"], "prompt": p})
        L += [f"## {it['id']} {it['name_ko']} ({it['category']})", "", "```", p, "```", ""]
    open(os.path.join(OUT, "C3_프롬프트_아이템.md"), "w", encoding="utf-8").write("\n".join(L))
    # C4 배경·컷신·UI
    L = ["# 부록 C4. 미드저니 프롬프트 — 배경·컷신·UI", "", "## 1. 국가 키 아트 (24) · 지역 전투 보드 배경 (120)", ""]
    for n in nations["nations"]:
        nk = n["key"]; p = PAL[nk]
        key = f"wide establishing shot of {p['env']}, iconic capital landmark, epic scale, {pal(nk)}, {MOOD} --ar 16:9 --stylize 250 --sref {SREF['bg']} {NEG}"
        prompts["backgrounds"].append({"id": f"BG-NATION-KEY-{nk}", "prompt": key})
        L += [f"### {n['name_ko']} — BG-NATION-KEY-{nk}", "", "```", key, "```", ""]
        for i, (reg, desc) in enumerate(zip(n["regions"], REGION_DESC[nk])):
            bp = (f"battle arena background for a hex-grid autobattler, {desc}, {p['env'].split(',')[0]}, wide shot with an open flat ground area in the center kept low-contrast and low-saturation for unit readability, "
                  f"atmospheric detail at the edges, {pal(nk)}, {MOOD} --ar 16:9 --stylize 200 --sref {SREF['bg']} {NEG}")
            prompts["backgrounds"].append({"id": f"BG-BOARD-{nk}-{i+1}", "region": reg, "prompt": bp})
            L += [f"**BG-BOARD-{nk}-{i+1} {reg}**", "", "```", bp, "```", ""]
    L += ["## 2. 스토리 컷신 (25)", ""]
    for cid, act, desc in CUTSCENES:
        cp = f"cinematic story illustration, {desc}, {MOOD} --ar 16:9 --stylize 300 --sref {SREF['cutscene']} {NEG}"
        prompts["cutscenes"].append({"id": cid, "act": act, "prompt": cp})
        L += [f"**{cid} (막 {act})**", "", "```", cp, "```", ""]
    L += ["## 3. 타이틀·로비·월드맵·UI 장식", ""]
    ui = [
        ("BG-TITLE", f"title key art, a wandering mercenary man with two swords standing on an ash plain facing a colossal black dragon in a burning sky, an azure dragon rising behind him, {MOOD} --ar 16:9 --stylize 300 --sref {SREF['cutscene']} {NEG}"),
        ("UI-LOGO", f"fantasy game logo emblem, ash-grey dragon wing wrapped around an ember flame, bronze and gold metal, no letters, centered on black, {MOOD.replace('no text', 'no letters')} --ar 3:1 --stylize 250 --sref {SREF['ui']} {NEG}"),
        ("BG-LOBBY", f"interior of a mercenary guild hall in a free city, long wooden tables, wolf banners, bounty board, fireplace, wide panoramic composition with empty foreground floor for characters, {pal('bromel')}, {MOOD} --ar 21:9 --stylize 200 --sref {SREF['bg']} {NEG}"),
        ("BG-WORLDMAP", f"painted parchment world map of a fantasy continent with 24 nations, mountains, forests, deserts, a frozen north, a hidden sky island, a volcanic south and an ash wasteland, hand-drawn cartography style with painterly terrain, no labels, {MOOD} --ar 16:3 --stylize 220 --sref {SREF['bg']} {NEG}"),
        ("UI-FRAME-ORNAMENT", f"ornamental UI frame corner set, dragon-scale and bone motifs with ember inlays, bronze metal on black, flat front view, tileable borders, {MOOD.replace('cinematic composition, ', '')} --ar 1:1 --stylize 120 --sref {SREF['ui']} {NEG}"),
        ("UI-BANNER-WIN", f"victory banner ornament, golden laurel of dragon scales with ember particles, horizontal, centered on black, no letters, {MOOD} --ar 4:1 --stylize 180 --sref {SREF['ui']} {NEG}"),
        ("UI-BANNER-LOSE", f"defeat banner ornament, cracked ash-grey dragon scales with dying embers, horizontal, centered on black, no letters, {MOOD} --ar 4:1 --stylize 180 --sref {SREF['ui']} {NEG}"),
        ("UI-BOUNTY-PAPER", f"old bounty poster parchment texture with wax seal and torn edges, blank center area, flat front view, {MOOD.replace('cinematic composition, ', '')} --ar 3:4 --stylize 100 --sref {SREF['ui']} {NEG}"),
        ("UI-FRAME-TIER", f"set of five ornate square portrait frames in increasing grandeur: plain iron, bronze with leaves, silver with blue gems, violet-enameled gold, legendary gold with ember glow; flat front view on black, {MOOD.replace('cinematic composition, ', '')} --ar 5:1 --stylize 120 --sref {SREF['ui']} {NEG}"),
    ]
    for cid, cp in ui:
        prompts["ui"].append({"id": cid, "prompt": cp})
        L += [f"**{cid}**", "", "```", cp, "```", ""]
    L += ["## 4. 벡터 아이콘 참고(미드저니는 참고용, 최종은 Figma 벡터)", "",
          "```", f"icon set sheet, 24 battle-type glyphs (skirmish, siege, defense, escort, hunt, duel, ambush, expedition, bounty, invasion, survival, encounter, trial, raid, rescue, assassination, strike, suppression, monster hunt, decisive, arena, escape, recon, guard), two-tone ivory on dark slate, 4px line weight, 64px grid, flat, no text --ar 4:3 --stylize 60 --sref {SREF['ui']} {NEG}", "```", "",
          "```", f"heraldic emblem set, 14 faction crests (knight kingdom lily, northern wolf-rune, eastern cherry-and-sword, desert crescent-dagger, maritime anchor-wave, elven leaf-bow, dwarven hammer-gear, hi-tech hexagon-circuit, necromantic skull-moon, sky-star sigil, dragon scale-flame, tribal bone-axe, holy sun-cross, mercenary grey wolf), two-tone metal on dark, flat, no text --ar 4:3 --stylize 80 --sref {SREF['ui']} {NEG}", "```", ""]
    open(os.path.join(OUT, "C4_프롬프트_배경_UI_컷신.md"), "w", encoding="utf-8").write("\n".join(L))
    json.dump(prompts, open(os.path.join(ROOT, "data", "prompts.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    missing = [h["name_ko"] for h in heroes["heroes"] if h["name_ko"] not in HERO_DESC]
    print("heroes", len(prompts["heroes"]), "monsters", len(prompts["monsters"]), "items", len(prompts["items"]), "backgrounds", len(prompts["backgrounds"]), "cutscenes", len(prompts["cutscenes"]), "ui", len(prompts["ui"]), "missing hero desc:", missing)


if __name__ == "__main__":
    main()
