local RS = RecipeScan

RS.EXPORT_NAME = "RecipeScan"

-- strips the format's separators from a field
local function Clean(s)
	local out = string.gsub(tostring(s or ""), "[;,\r\n]", " ")
	return out
end

local function SortedKeys(t)
	local keys = {}
	for k in pairs(t) do table.insert(keys, k) end
	table.sort(keys)
	return keys
end

-- RS1 text: one char line per character, followed by its prof lines
function RS:BuildExport()
	local lines = { "RS1" }
	local chars = RecipeScanDB.chars
	local charKeys = SortedKeys(chars)
	for ci = 1, table.getn(charKeys) do
		local c = chars[charKeys[ci]]
		table.insert(lines, "char;" .. Clean(c.realm) .. ";" .. Clean(c.name) .. ";" .. Clean(c.faction)
			.. ";" .. Clean(c.class) .. ";" .. Clean(c.race) .. ";" .. (tonumber(c.scannedAt) or 0))
		local profKeys = SortedKeys(c.professions)
		for pi = 1, table.getn(profKeys) do
			local p = c.professions[profKeys[pi]]
			if type(p) == "table" and type(p.ids) == "table" then
				table.insert(lines, "prof;" .. Clean(profKeys[pi]) .. ";" .. (tonumber(p.rank) or "")
					.. ";" .. (tonumber(p.max) or "") .. ";" .. Clean(p.kind) .. ";" .. table.concat(p.ids, ","))
			end
		end
	end
	return table.concat(lines, "\n") .. "\n"
end

function RS:HasFileExport()
	return type(ExportFile) == "function"
end

-- SuperWoW: writes <WoW>\Imports\RecipeScan.txt (overwrites)
function RS:ExportToFile()
	if not self:HasFileExport() then return false end
	ExportFile(self.EXPORT_NAME, self:BuildExport())
	return true
end

function RS:BuildCopyFrame()
	local f = CreateFrame("Frame", "RecipeScanCopyFrame", UIParent)
	f:SetWidth(520)
	f:SetHeight(360)
	f:SetPoint("CENTER", UIParent, "CENTER", 0, 0)
	f:SetFrameStrata("DIALOG")
	f:SetBackdrop({
		bgFile = "Interface\\DialogFrame\\UI-DialogBox-Background",
		edgeFile = "Interface\\DialogFrame\\UI-DialogBox-Border",
		tile = true, tileSize = 32, edgeSize = 32,
		insets = { left = 11, right = 12, top = 12, bottom = 11 },
	})
	f:EnableMouse(true)
	f:SetMovable(true)
	f:RegisterForDrag("LeftButton")
	f:SetScript("OnDragStart", function() this:StartMoving() end)
	f:SetScript("OnDragStop", function() this:StopMovingOrSizing() end)
	table.insert(UISpecialFrames, "RecipeScanCopyFrame")

	local title = f:CreateFontString(nil, "OVERLAY", "GameFontNormal")
	title:SetPoint("TOP", f, "TOP", 0, -18)
	title:SetText("RecipeScan export: Ctrl+C, then paste on the website")

	local close = CreateFrame("Button", nil, f, "UIPanelCloseButton")
	close:SetPoint("TOPRIGHT", f, "TOPRIGHT", -6, -6)

	local sf = CreateFrame("ScrollFrame", "RecipeScanCopyScroll", f, "UIPanelScrollFrameTemplate")
	sf:SetPoint("TOPLEFT", f, "TOPLEFT", 20, -42)
	sf:SetPoint("BOTTOMRIGHT", f, "BOTTOMRIGHT", -40, 20)

	local eb = CreateFrame("EditBox", "RecipeScanCopyEdit", sf)
	eb:SetMultiLine(true)
	eb:SetMaxLetters(0)
	eb:SetAutoFocus(false)
	eb:SetFontObject(ChatFontNormal)
	eb:SetWidth(450)
	eb:SetHeight(300)
	eb:SetScript("OnEscapePressed", function() this:ClearFocus() this:GetParent():GetParent():Hide() end)
	sf:SetScrollChild(eb)

	f.edit = eb
	return f
end

function RS:ShowCopyBox()
	if not self.copyFrame then self.copyFrame = self:BuildCopyFrame() end
	local f = self.copyFrame
	f.edit:SetText(self:BuildExport())
	f:Show()
	f.edit:SetFocus()
	f.edit:HighlightText()
end
