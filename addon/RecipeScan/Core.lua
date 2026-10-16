RecipeScan = RecipeScan or {}
local RS = RecipeScan

RS.version = GetAddOnMetadata("RecipeScan", "Version")
RS.open = {}

function RS:Print(msg)
	DEFAULT_CHAT_FRAME:AddMessage("|cff33ccffRecipeScan:|r " .. msg)
end

function RS:EnsureDB()
	if type(RecipeScanDB) ~= "table" then RecipeScanDB = {} end
	local db = RecipeScanDB
	if type(db.chars) ~= "table" then db.chars = {} end
	if db.autoExport == nil then db.autoExport = true end
	-- drop malformed character entries
	for key, c in pairs(db.chars) do
		if type(c) ~= "table" then
			db.chars[key] = nil
		elseif type(c.professions) ~= "table" then
			c.professions = {}
		end
	end
end

function RS:CharKey()
	return GetRealmName() .. "-" .. UnitName("player")
end

-- returns the current character's entry, refreshing its identity fields
function RS:GetChar()
	local key = self:CharKey()
	local c = RecipeScanDB.chars[key]
	if type(c) ~= "table" then
		c = { professions = {} }
		RecipeScanDB.chars[key] = c
	end
	c.realm = GetRealmName()
	c.name = UnitName("player")
	c.faction = UnitFactionGroup("player")
	local _, classToken = UnitClass("player")
	c.class = classToken
	local _, raceToken = UnitRace("player")
	c.race = raceToken
	return c
end
