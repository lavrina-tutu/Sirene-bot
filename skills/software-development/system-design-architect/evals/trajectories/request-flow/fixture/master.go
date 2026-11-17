package flow
type Offer struct { HotelID, ContractID string }
type CalcRequest struct { HotelID, ContractID string }
func ListingMapper(o Offer) CalcRequest {return CalcRequest{HotelID:o.HotelID}}
func DetailMapper(o Offer) CalcRequest {return CalcRequest{HotelID:o.HotelID,ContractID:o.ContractID}}
func Calculate(r CalcRequest, enabled bool, active map[string]bool) bool {
 if !enabled || r.ContractID=="" {return true};return active[r.ContractID]
}
