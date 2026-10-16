local RS = RecipeScan

-- "item", 10050 / "enchant", 57146 from a hyperlink
local function ParseLinkId(link)
	if not link then return nil end
	local _, _, kind, id = string.find(link, "H(%a+):(%d+)")
	if not kind then return nil end
	return kind, tonumber(id)
end

-- nil when "all" is selected, else the list of enabled indices
local function SaveFilter(getFn, listFn)
	if getFn(0) then return nil end
	local on = {}
	local n = table.getn({ listFn() })
	for i = 1, n do
		if getFn(i) then table.insert(on, i) end
	end
	return on
end

local function RestoreFilter(setFn, on)
	if not on then return end
	for j = 1, table.getn(on) do
		if j == 1 then setFn(on[j], 1, 1) else setFn(on[j], 1) end
	end
end

function RS:StoreProfession(prof, rank, maxRank, kind, ids, noLink)
	table.sort(ids)
	local c = self:GetChar()
	local old = c.professions[prof]
	local oldCount = old and type(old.ids) == "table" and table.getn(old.ids)
	c.professions[prof] = { rank = rank, max = maxRank, kind = kind, ids = ids }
	c.scannedAt = time()
	self.scanCount = (self.scanCount or 0) + 1
	local count = table.getn(ids)
	if count ~= oldCount then
		local msg = prof .. ": " .. count .. " recipes saved"
		if noLink > 0 then msg = msg .. " (" .. noLink .. " without link)" end
		self:Print(msg)
	end
	if RecipeScanDB.autoExport then self:ExportToFile() end
end

-- reads every recipe; restores filters and collapsed headers afterwards
function RS:ScanTradeSkill()
	local prof, rank, maxRank = GetTradeSkillLine()
	if not prof or prof == "UNKNOWN" then return end
	self.scanning = true

	local collapsed = {}
	for i = 1, GetNumTradeSkills() do
		local name, kind, _, expanded = GetTradeSkillInfo(i)
		if kind == "header" and not expanded then collapsed[name] = true end
	end
	local sub = SaveFilter(GetTradeSkillSubClassFilter, GetTradeSkillSubClasses)
	local slot = SaveFilter(GetTradeSkillInvSlotFilter, GetTradeSkillInvSlots)

	SetTradeSkillSubClassFilter(0, 1, 1)
	SetTradeSkillInvSlotFilter(0, 1, 1)
	ExpandTradeSkillSubClass(0)

	local ids, seen, noLink = {}, {}, 0
	for i = 1, GetNumTradeSkills() do
		local _, kind = GetTradeSkillInfo(i)
		if kind ~= "header" then
			local linkKind, id = ParseLinkId(GetTradeSkillItemLink(i))
			if linkKind == "item" then
				if not seen[id] then seen[id] = true table.insert(ids, id) end
			else
				noLink = noLink + 1
			end
		end
	end

	-- from the end: collapsing shifts the rows below
	for i = GetNumTradeSkills(), 1, -1 do
		local name, kind = GetTradeSkillInfo(i)
		if kind == "header" and collapsed[name] then CollapseTradeSkillSubClass(i) end
	end
	RestoreFilter(SetTradeSkillSubClassFilter, sub)
	RestoreFilter(SetTradeSkillInvSlotFilter, slot)

	self:StoreProfession(prof, rank, maxRank, "item", ids, noLink)
end

-- Enchanting; the Craft list has no headers (live check C16)
function RS:ScanCraft()
	local prof, rank, maxRank = GetCraftDisplaySkillLine()
	if not prof then return end
	self.scanning = true

	local ids, seen, noLink = {}, {}, 0
	for i = 1, GetNumCrafts() do
		local _, _, kind = GetCraftInfo(i)
		if kind ~= "header" then
			local linkKind, id = ParseLinkId(GetCraftItemLink(i))
			if linkKind == "enchant" then
				if not seen[id] then seen[id] = true table.insert(ids, id) end
			else
				noLink = noLink + 1
			end
		end
	end

	self:StoreProfession(prof, rank, maxRank, "spell", ids, noLink)
end
