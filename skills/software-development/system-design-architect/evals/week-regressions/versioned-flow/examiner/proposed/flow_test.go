package flow
import "testing"
func TestPathMatrix(t *testing.T){
 offer:=Import(ProviderOffer{"h7","c9"});if offer.ContractID!="c9"{t.Fatal("lost internal contract")}
 for _,tc:=range []struct{name string;enabled bool;active map[string]bool;listing,detail bool}{
  {"active",true,map[string]bool{"c9":true},true,true},
  {"inactive",true,map[string]bool{"c8":true},false,false},
  {"disabled",false,map[string]bool{"c8":true},true,true},
 }{t.Run(tc.name,func(t *testing.T){
  if got:=Calculate(ListingMapper(offer),tc.enabled,tc.active);got!=tc.listing{t.Fatalf("listing %v",got)}
  if got:=Calculate(DetailMapper(offer),tc.enabled,tc.active);got!=tc.detail{t.Fatalf("detail %v",got)}
 })}
}
