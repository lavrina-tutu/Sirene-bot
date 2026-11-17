package flow
type ProviderOffer struct{ HotelID,LegalID string }
type Offer struct{ HotelID,ContractID string }
type CalcRequest struct{ HotelID,ContractID string }
func Import(p ProviderOffer)Offer{return Offer{HotelID:p.HotelID,ContractID:p.LegalID}}
