package flow
type BindingOwner interface { Current(hotel string) (contract string,err error) }
