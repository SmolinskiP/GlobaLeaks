export class TokenResponse {
  token_id: string;
  token_id_ans: number;

  constructor(token_id: string, token_id_ans: number){
    this.token_id = token_id
    this.token_id_ans = token_id_ans
  }
}