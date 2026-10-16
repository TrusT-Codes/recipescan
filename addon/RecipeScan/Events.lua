local RS = RecipeScan

local DEBOUNCE = 0.5
-- ignores *_UPDATE events the scan's own expand/filter calls fire
local QUIET = 0.3

local function Run(name, fn)
	local ok = xpcall(fn, function(msg)
		geterrorhandler()("RecipeScan " .. name .. ": " .. tostring(msg))
	end)
	RS.scanning = nil
	RS.quietUntil = GetTime() + QUIET
	return ok
end

function RS:Scan(which)
	if self.timer then self.timer:Cancel() self.timer = nil end
	if which == "trade" then
		Run("trade scan", function() RS:ScanTradeSkill() end)
	else
		Run("craft scan", function() RS:ScanCraft() end)
	end
end

-- restarts the debounce on every update
function RS:QueueScan(which)
	if self.scanning or GetTime() < (self.quietUntil or 0) then return end
	if self.timer then self.timer:Cancel() end
	self.timer = C_Timer.NewTimer(DEBOUNCE, function()
		RS.timer = nil
		if RS.open[which] then RS:Scan(which) end
	end)
end

function RS:RunLogin()
	if type(C_Timer) ~= "table" then
		self:Print("ClassicAPI not found - addon disabled.")
		return
	end
	self:EnsureDB()
	self.loginDone = true
end

local f = CreateFrame("Frame")
f:RegisterEvent("PLAYER_LOGIN")
f:RegisterEvent("TRADE_SKILL_SHOW")
f:RegisterEvent("TRADE_SKILL_UPDATE")
f:RegisterEvent("TRADE_SKILL_CLOSE")
f:RegisterEvent("CRAFT_SHOW")
f:RegisterEvent("CRAFT_UPDATE")
f:RegisterEvent("CRAFT_CLOSE")
f:SetScript("OnEvent", function()
	local ev = event
	if ev == "PLAYER_LOGIN" then
		RS:RunLogin()
		return
	end
	if not RS.loginDone then return end
	if ev == "TRADE_SKILL_SHOW" then
		RS.open.trade = true
		RS:Scan("trade")
	elseif ev == "TRADE_SKILL_UPDATE" then
		if RS.open.trade then RS:QueueScan("trade") end
	elseif ev == "TRADE_SKILL_CLOSE" then
		RS.open.trade = nil
	elseif ev == "CRAFT_SHOW" then
		RS.open.craft = true
		RS:Scan("craft")
	elseif ev == "CRAFT_UPDATE" then
		if RS.open.craft then RS:QueueScan("craft") end
	elseif ev == "CRAFT_CLOSE" then
		RS.open.craft = nil
	end
end)

local function PrintStatus()
	local n = 0
	for _ in pairs(RecipeScanDB.chars) do n = n + 1 end
	RS:Print("v" .. tostring(RS.version) .. ", " .. n .. " character(s), auto export "
		.. (RecipeScanDB.autoExport and "on" or "off") .. ", file export "
		.. (RS:HasFileExport() and "available" or "not available") .. ", scans " .. (RS.scanCount or 0))
	local c = RecipeScanDB.chars[RS:CharKey()]
	if not c then return end
	for prof, p in pairs(c.professions) do
		RS:Print("  " .. prof .. " " .. tostring(p.rank) .. "/" .. tostring(p.max) .. ": " .. table.getn(p.ids) .. " recipes")
	end
end

SLASH_RECIPESCAN1 = "/recipescan"
SLASH_RECIPESCAN2 = "/rscan"
SlashCmdList["RECIPESCAN"] = function(msg)
	if not RS.loginDone then RS:Print("still loading") return end
	local _, _, cmd, rest = string.find(msg or "", "^(%S*)%s*(.-)$")
	cmd = string.lower(cmd or "")
	if cmd == "export" then
		if RS:ExportToFile() then
			RS:Print("written to <WoW folder>\\Imports\\" .. RS.EXPORT_NAME .. ".txt")
		else
			RS:ShowCopyBox()
		end
	elseif cmd == "copy" then
		RS:ShowCopyBox()
	elseif cmd == "auto" then
		RecipeScanDB.autoExport = (rest == "on")
		RS:Print("auto export " .. (RecipeScanDB.autoExport and "on" or "off"))
	elseif cmd == "status" then
		PrintStatus()
	elseif cmd == "forget" and rest ~= "" then
		if RecipeScanDB.chars[rest] then
			RecipeScanDB.chars[rest] = nil
			RS:Print("removed " .. rest)
		else
			RS:Print("no character " .. rest .. " (use Realm-Name)")
		end
	else
		RS:Print("open a profession window to scan it. Commands:")
		RS:Print("  /recipescan export - write Imports\\RecipeScan.txt (or show copy box)")
		RS:Print("  /recipescan copy - show copy box")
		RS:Print("  /recipescan auto on|off - export after every scan")
		RS:Print("  /recipescan status - saved characters and professions")
		RS:Print("  /recipescan forget Realm-Name - delete a character")
	end
end
