package flow
func Calculate(r CalcRequest,enabled bool,active map[string]bool)bool{
 if !enabled || r.ContractID==""{return true};return active[r.ContractID]
}
